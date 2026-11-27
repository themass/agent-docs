"""回合执行（D §6.2–6.5、§7.3）。

一个回合 = 一把锁 + 一个 turn_id。本进程负责：
- 续租锁（每 10 秒）；
- 读取 turn:{tid}:ctl：merge 在首个可见 token（或第一个工具调用）之前中止并用同一 turn_id 重跑；
  steer 进收件箱；cancel 中止；
- 维护 phase（pre_output → output → tool），只前进不回退（撤销合并时例外，见下）；
- 把回合覆盖的用户消息挂到回合上（attach_turn，见 D §3.3）；
- 增量合并写 message.delta（50 毫秒或 64 字符一次），正文另存 turn:{tid}:text；
- 结束时落库助手消息、释放锁、尝试排空。

竞态（评审后修正）：Lua 判定「合并」时阶段是 pre_output，但控制消息由后台协程读取，
首 token 可能先于读取到达。因此在输出开始前（以及第一个工具调用前）**同步**读取控制流：
1. 先同步读一次，有合并请求就中止本次模型调用；
2. 把阶段推进到 output；
3. 再同步读一次：如果恰好夹在两步之间有合并，撤销阶段（退回 pre_output）并中止。
Lua 与阶段推进在 Redis 中是线性的，所以任何被 Lua 判为合并的消息，都一定能被这两次同步读取看到。

produce 由 bootstrap 注入（把 DeerFlow 的事件流接进来），这里不认识 LangGraph。

锁丢失（续租失败）：立即停止产出，不写助手消息，按失败收尾。写回复时还带围栏号做条件写，
锁过期后被别的进程接手的旧回合因此写不进来（chat-agent-context-design.md §4.2）。

after_turn：收尾时、**释放锁之前**调用（拿着锁，才能安全地改对话线程，例如补记被中断的回复）。
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from companion.service.chat.lifecycle import DrainState
from companion.service.turn.queue import TurnPhase
from companion.agent.brain.steer import SteerInbox
from companion.agent.text.display_cleaner import DisplayTextCleaner
from companion.agent.brain.port import (
    BrainEvent,
    GraphMessageIds,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnInputMessage,
    TurnRequest,
)
from companion.db.port import MessageStore, QueueStore
from companion import metrics
from companion.service.turn.control import TurnControlPort

log = logging.getLogger("companion.turn")

LOCK_RENEW_SEC = 10.0
DELTA_FLUSH_SEC = 0.05
DELTA_FLUSH_CHARS = 64
MAX_RESTARTS = 2

#: 回合级 wall-clock 兜底（2026-11-28 生产挂死）。此前回合从头到尾没有任何总时长闸：
#: 大脑流或工具里的任何一个 await 挂死（Redis/TOS/下游工具都没有自己的超时时就是永久挂死），
#: 持锁任务永远不返回，续租把锁一直续活——终止事件永远发不出去，锁永远不放，
#: 该会话的下一条消息只能等锁 TTL 加恢复流程。闸放在 ``_run`` 的整个回合体上
#: （读输入 + 挂接 + 全部尝试 + 重跑），300 秒：正常回合（含多轮工具）离这个量级还差
#: 一个数量级，不会误伤；挂死的回合则最多多占一个会话 5 分钟就自动恢复。
#: Redis 与 TOS 各自的命令级超时（见 bootstrap/redis_client.py、uploads/tos.py）
#: 在更细的粒度上先兜住大部分挂点，这里是最后一道闸。
TURN_WALL_CLOCK_SEC = 300.0

Produce = Callable[[TurnRequest, SteerInbox], AsyncIterator[BrainEvent]]
Drain = Callable[..., Awaitable[None]]


def _attachment_ids(meta: Any) -> tuple[str, ...]:
    """从消息 meta 里取出附件 upload_id，按发送顺序。坏数据一律跳过，不因为一条脏附件让整个回合失败。"""
    if not isinstance(meta, dict):
        return ()
    items = meta.get("attachments")
    if not isinstance(items, list):
        return ()
    ids: list[str] = []
    for item in items:
        if isinstance(item, dict):
            upload_id = item.get("upload_id")
            if isinstance(upload_id, str) and upload_id:
                ids.append(upload_id)
    return tuple(ids)


def _location_from_meta(meta: Any) -> dict[str, float] | None:
    """提取并验证消息的结构化位置；坏历史数据当作无位置处理。"""
    if not isinstance(meta, dict) or not isinstance(meta.get("location"), dict):
        return None
    location = meta["location"]
    lat, lng = location.get("lat"), location.get("lng")
    if (not isinstance(lat, (int, float)) or isinstance(lat, bool)
            or not isinstance(lng, (int, float)) or isinstance(lng, bool)
            or not -90 <= lat <= 90 or not -180 <= lng <= 180):
        return None
    result = {"lat": float(lat), "lng": float(lng)}
    accuracy = location.get("accuracy_m")
    if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool) and 0 <= accuracy <= 100_000:
        result["accuracy_m"] = float(accuracy)
    return result


def _channel_for(inputs: list[TurnInputMessage]) -> str:
    """一条回合里只要有语音输入就按语音算。

    语音回合 ``steerable=False``，不会和文字输入合并，所以「任一为语音」与
    「全部为语音」等价；按任一判断是为了合并不上线时也不会把语音当文字处理。
    """
    return "voice" if any(i.kind == "voice" for i in inputs) else "text"


@dataclass(frozen=True)
class TurnOutcome:
    """一个回合结束时的事实，交给 after_turn（记忆写入、补记中断回复等）。"""

    owner_id: int
    session_id: int
    character_id: str
    turn_id: str
    user_message_ids: tuple[int, ...]
    user_text: str
    assistant_message_id: int | None
    assistant_text: str
    interrupted: bool
    cancelled: bool
    failed: bool
    lock_lost: bool
    lc_ids: tuple[str, ...]
    #: 打断时「已说出口」的文本前缀（契约 v2 §2.2）：按端侧 played_ms 折算的段前缀。
    #: 没有端侧上报时为 ``""``——after_turn 退回 assistant_text，与改动前一致。
    spoken_prefix: str = ""


AfterTurn = Callable[[TurnOutcome], Awaitable[None]]


@dataclass
class TurnInput:
    owner_id: int
    session_id: int
    character_id: str
    turn_id: str
    owner: str                 # 锁持有者，形如 "{process}:{turn_id}"
    text: str
    message_ids: list[int]     # 启动时覆盖的用户消息（排空时可能有多条）
    fence: int | None = None   # 拿锁时取得的围栏号；None 表示不做围栏检查
    alt_of: int | None = None  # 重新生成：被重生成的助手回复 id；新回复作为它的另一个候选保存


@dataclass
class _RunState:
    merge_requested: bool = False
    merged: list[tuple[int, str]] = field(default_factory=list)
    steer_pushed: list[int] = field(default_factory=list)
    cancelled: bool = False
    output_started: bool = False
    deltas: list[str] = field(default_factory=list)     # 展示文本（协议片段已剥成 say）
    pending: str = ""                                    # 待发帧的展示文本
    pending_raw: str = ""                                # 待发帧的原始文本（语音回合的 raw_delta）
    last_flush: float = field(default_factory=time.monotonic)
    ctl_last: str = "0-0"      # 已处理的最后一条控制消息 id（去重用）
    lost: bool = False         # 续租失败：这把锁已经不是我们的
    closed: bool = False       # 收尾已走到「终止事件+放锁」至少一次尝试成功（紧急路径据此判断）
    lc_ids: list[str] = field(default_factory=list)   # 大脑写进对话线程的消息 id（跨重跑累计）
    started: float = field(default_factory=time.monotonic)   # 回合开始，用来算用户等了多久
    first_output_at: float | None = None                     # 第一个可见 token 的时刻
    # 协议片段清洗：落库/发布的是 say 文本，原文只走 raw_delta（见 display_cleaner）。
    cleaner: DisplayTextCleaner = field(default_factory=DisplayTextCleaner)

    def restart(self) -> None:
        self.merge_requested = False
        self.merged = []
        self.output_started = False
        self.deltas = []
        self.pending = ""
        self.pending_raw = ""
        self.last_flush = time.monotonic()
        self.cleaner = DisplayTextCleaner()   # 半截片段不能带进重跑后的那一遍


def _id_after(a: str, b: str) -> bool:
    """Redis Stream id 比较：'<毫秒>-<序号>'。"""
    def key(v: str) -> tuple[int, int]:
        ms, _, seq = v.partition("-")
        return int(ms or 0), int(seq or 0)
    return key(a) > key(b)


class TurnRunner:
    def __init__(
        self,
        *,
        control: TurnControlPort,
        messages: MessageStore,
        queue: QueueStore,
        produce: Produce,
        drain: Drain | None = None,
        tracker: DrainState | None = None,
        steer_budget: int = 3,
        after_turn: AfterTurn | None = None,
        uploads: Any = None,
    ) -> None:
        self._after_turn = after_turn
        self._control = control
        self._messages = messages
        self._queue = queue
        self._produce = produce
        self._drain = drain
        self._tracker = tracker
        self._steer_budget = steer_budget
        # 附件读取器（UploadService）：要 get_owned + read_bytes。没配 TOS 时为 None，
        # 此时回合照常跑，只是模型看不到图（上传接口本身也没挂）。
        self._uploads = uploads

    async def run(self, inp: TurnInput) -> None:
        if self._tracker is not None:
            self._tracker.turn_started()
        started = time.monotonic()
        try:
            with metrics.turn_in_flight():
                await self._run(inp, started=started)
        finally:
            if self._tracker is not None:
                self._tracker.turn_finished()

    async def _run(self, inp: TurnInput, *, started: float) -> None:
        state = _RunState()
        inbox = SteerInbox(budget=self._steer_budget)
        stop = asyncio.Event()
        renew: asyncio.Task | None = None
        watch: asyncio.Task | None = None
        failed = False
        timed_out = False
        # wall-clock 兜底（TURN_WALL_CLOCK_SEC 的取值理由见常数注释）：罩住「读输入 +
        # 挂接 + 全部尝试」的整个回合体。``_finish`` 刻意留在闸**之外**——到点时恰恰
        # 需要收尾（终止事件+放锁）能跑完，把收尾也包进闸里就会被一起掐掉，
        # 「永不终结」换成「终结但没人放锁」，更糟。续租/watch 在下面 finally 里
        # 无条件停：超时收尾时不许再把一把没人认领的锁续活。
        try:
            async with asyncio.timeout(TURN_WALL_CLOCK_SEC) as clock:
                # ⓪ 段探针：turn 任务被拉起后到进模型前还有两次串行库往返（读消息 + attach_turn），
                # 原先没有日志，`turn.started` 与 `voice llm start` 之间是黑的。
                prelude_started = time.monotonic()
                inputs = await self._load_inputs(inp)
                restarts = 0
                renew = asyncio.create_task(self._renew(inp, state, stop))
                watch = asyncio.create_task(self._watch_ctl(inp, inbox, state, stop))
                await self._messages.attach_turn(owner_id=inp.owner_id, session_id=inp.session_id,
                                                 message_ids=inp.message_ids, turn_id=inp.turn_id)
                log.info("turn prelude ms=%d inputs=%d",
                         int((time.monotonic() - prelude_started) * 1000), len(inputs))
                # turn.started 不在这里发：已在 SubmitService._start() 里、启动本任务之前发出，
                # 并与 message.created 合成了一次 Redis 往返。这里再发一次就是重复事件。
                while True:
                    outcome = await self._attempt(inp, inputs, inbox, state)
                    if outcome != "merged":
                        break
                    if restarts >= MAX_RESTARTS:
                        # 重跑次数用尽：合并进来的输入不能再进这个回合，改为排队（D §6.3）。
                        for message_id, text in state.merged:
                            await self._requeue(inp, message_id, text)
                        break
                    restarts += 1
                    metrics.count_restart()
                    await self._attach_merged(inp, state)
                    inputs = inputs + [TurnInputMessage(message_id=mid, text=text) for mid, text in state.merged]
                    state.restart()  # 原地重置：控制协程持有的是同一个对象
                    await self._control.publish(
                        session_id=inp.session_id, event="turn.restarted",
                        data={"turn_id": inp.turn_id,
                              "user_message_ids": inp.message_ids + [m for m, _ in state.merged]})
        except TimeoutError:
            # 闸到点时 asyncio.timeout 抛的就是这里；redis-py 的命令级超时是
            # redis.exceptions.TimeoutError（RedisError 的子类，不是内建 TimeoutError），
            # 走下面 except Exception。再用 ``clock.expired()`` 排除其它库抛的普通
            # TimeoutError——只有闸本身到点才算 wall-clock 终结。
            failed = True
            if clock.expired():
                log.error("turn wall-clock exceeded sec=%s", TURN_WALL_CLOCK_SEC,
                          extra={"turn_id": inp.turn_id})
                timed_out = True
            else:
                log.exception("turn failed", extra={"turn_id": inp.turn_id})
        except Exception:
            log.exception("turn failed", extra={"turn_id": inp.turn_id})
            failed = True
        finally:
            if failed:
                # 终止事件尽力发（发不出去也不能挡住 _finish 放锁）。code 区分两种结局：
                # turn_timeout = wall-clock 闸到点（回合体挂死被兜底掐断）；
                # turn_failed = 其它异常。两者对客户端都是「可重试的回答中断」。
                try:
                    await self._control.publish(
                        session_id=inp.session_id, event="error",
                        data={"turn_id": inp.turn_id,
                              "code": "turn_timeout" if timed_out else "turn_failed",
                              "message": "回答中断，请重试", "retryable": True})
                except Exception:  # noqa: BLE001 —— _finish 的紧急路径还会再试一次终止事件
                    log.exception("turn error publish failed", extra={"turn_id": inp.turn_id})
            stop.set()
            for task in (renew, watch):
                if task is not None:
                    task.cancel()
            await asyncio.gather(*[t for t in (renew, watch) if t is not None],
                                 return_exceptions=True)
            # 收尾只执行一次：无论成功、失败、超时，锁都必须释放。
            # _finish 内部自带兜底（任何一步抛错都还有紧急路径），不许把异常抛穿这里。
            await self._finish(inp, state, inbox, failed=failed)

    # ---- 一次模型调用 ----

    async def _load_inputs(self, inp: TurnInput) -> list[TurnInputMessage]:
        """本回合覆盖的用户消息，逐条带 id（排空时有多条）。没有消息 id 的重跑（如「继续」）返回空，
        由大脑用 ``message`` 字段兜底。

        附件在消息的 ``meta["attachments"]`` 里（``UploadService`` 落库时写的 upload_id 列表），
        这里原样带到 ``TurnInputMessage.upload_ids``：图是不是真能读，到大脑构造消息时才知道。
        """
        loaded: list[TurnInputMessage] = []
        for mid in inp.message_ids:
            record = await self._messages.get(owner_id=inp.owner_id, message_id=mid)
            if record is not None:
                loaded.append(TurnInputMessage(message_id=mid, text=record.content,
                                               upload_ids=_attachment_ids(record.meta),
                                               kind=getattr(record, "kind", "") or "chat",
                                               location=_location_from_meta(record.meta)))
        if inp.message_ids and not loaded:
            loaded = [TurnInputMessage(message_id=inp.message_ids[0], text=inp.text)]
        return loaded

    async def _load_images(self, inp: TurnInput,
                           inputs: list[TurnInputMessage]) -> dict[int, tuple[str, ...]]:
        """把本回合的**图片**附件读成 data URL，键是消息主键。

        每个 upload_id 先按归属查一次（``uploads.get_owned``），别人的 id 一律当作不存在——
        否则只要猜中一个 ULID 就能让模型看别人的图。读不到、不是图片、存储没配置，
        都只跳过这一张并记一条日志：文字照常进模型，不因为一张图让整轮失败。

        mime 闸门（P2-13）在**读字节之前**：视频/文件附件的字节一旦 base64 进模型输入就是
        几十万 token 的账单，所以按 ca_upload 的 mime 判「是不是图片」，非图片直接跳过——
        判据用前缀而不是枚举 image 类型之外的东西，将来接文件消息时不用回来改这里。
        """
        if self._uploads is None:
            return {}
        result: dict[int, tuple[str, ...]] = {}
        for item in inputs:
            if not item.upload_ids:
                continue
            urls: list[str] = []
            for upload_id in item.upload_ids:
                record = await self._uploads.get_owned(owner_id=inp.owner_id, upload_id=upload_id)
                if record is None:
                    log.warning("attachment not owned or missing", extra={"upload_id": upload_id,
                                                                         "session_id": inp.session_id})
                    continue
                if not record.mime.startswith("image/"):
                    log.info("attachment skipped for model input (not an image)",
                             extra={"upload_id": upload_id, "mime": record.mime,
                                    "session_id": inp.session_id})
                    continue
                try:
                    data = await self._uploads.read_bytes(record=record)
                except Exception:
                    log.exception("attachment read failed", extra={"upload_id": upload_id,
                                                                   "object_key": record.object_key})
                    continue
                urls.append(f"data:{record.mime};base64,{base64.b64encode(data).decode('ascii')}")
            if urls:
                result[item.message_id] = tuple(urls)
        return result

    async def _attempt(self, inp: TurnInput, inputs: list[TurnInputMessage], inbox: SteerInbox,
                       state: _RunState) -> str:
        message = "\n\n".join(i.text for i in inputs) if inputs else inp.text
        request = TurnRequest(user_id=str(inp.owner_id), character_id=inp.character_id, message=message,
                              session_id=inp.session_id, inputs=tuple(inputs),
                              images=await self._load_images(inp, inputs),
                              metadata={"turn_id": inp.turn_id, "session_id": inp.session_id,
                                        # 输出层按来源渠道选：语音要口语短句、文字不要 cue JSON。
                                        "channel": _channel_for(inputs),
                                        # 合并回合采用时间上最新、带坐标的用户消息位置。
                                        "location": next((i.location for i in reversed(inputs) if i.location), None)})
        stream = self._produce(request, inbox)
        try:
            async for event in stream:
                if state.lost:
                    return "lost"
                if state.cancelled:
                    return "cancelled"
                if isinstance(event, GraphMessageIds):
                    state.lc_ids.extend(i for i in event.ids if i not in state.lc_ids)
                    continue
                if state.merge_requested and not state.output_started:
                    return "merged"
                if isinstance(event, TextDelta):
                    if not state.output_started and not await self._begin_output(inp, state, inbox):
                        return "merged"
                    await self._on_text(inp, state, event.text)
                elif isinstance(event, ToolStarted):
                    # 工具有副作用：只有在没有合并请求时才允许进入 TOOL 阶段。
                    await self._absorb(inp, state, inbox, await self._control.read_ctl_after(
                        turn_id=inp.turn_id, last_id=state.ctl_last))
                    if state.merge_requested and not state.output_started:
                        return "merged"
                    await self._control.advance_phase(session_id=inp.session_id, phase=TurnPhase.TOOL)
                    await self._control.publish(session_id=inp.session_id, event="step",
                                                data={"turn_id": inp.turn_id, "kind": "tool",
                                                      "title": event.name, "detail": "running"})
                elif isinstance(event, ToolFinished):
                    await self._control.publish(session_id=inp.session_id, event="step",
                                                data={"turn_id": inp.turn_id, "kind": "tool",
                                                      "title": event.name, "detail": "done"})
            await self._flush(inp, state)
            return "done"
        finally:
            await stream.aclose()

    async def _begin_output(self, inp: TurnInput, state: _RunState, inbox: SteerInbox) -> bool:
        """首个可见 token 之前的同步检查（见模块文档）。返回 False 表示必须中止并重跑。"""
        await self._absorb(inp, state, inbox, await self._control.read_ctl_after(
            turn_id=inp.turn_id, last_id=state.ctl_last))
        if state.merge_requested:
            return False
        await self._control.advance_phase(session_id=inp.session_id, phase=TurnPhase.OUTPUT)
        await self._absorb(inp, state, inbox, await self._control.read_ctl_after(
            turn_id=inp.turn_id, last_id=state.ctl_last))
        if state.merge_requested:
            # 夹在两步之间有合并：阶段退回 pre_output，本次调用中止，由调用方重跑。
            await self._control.set_phase(session_id=inp.session_id, phase=TurnPhase.PRE_OUTPUT)
            return False
        state.output_started = True
        if state.first_output_at is None:
            # 只记第一次：重跑之后那次的首字不是用户第一次看到字的时刻。
            state.first_output_at = time.monotonic()
        return True

    async def _on_text(self, inp: TurnInput, state: _RunState, text: str) -> None:
        # text 是模型原文；进气泡与落库的是剥掉协议片段后的 say。
        shown = state.cleaner.feed(text)
        state.deltas.append(shown)
        state.pending += shown
        state.pending_raw += text
        now = time.monotonic()
        if len(state.pending) >= DELTA_FLUSH_CHARS or now - state.last_flush >= DELTA_FLUSH_SEC:
            await self._flush(inp, state)

    async def _flush(self, inp: TurnInput, state: _RunState) -> None:
        if not state.pending and not state.pending_raw:
            return
        chunk, state.pending = state.pending, ""
        raw, state.pending_raw = state.pending_raw, ""
        state.last_flush = time.monotonic()
        data: dict[str, Any] = {"turn_id": inp.turn_id, "delta": chunk}
        # raw_delta 只在两串不一致的那帧出现（省流）。不按渠道开关：主动开口的
        # kind 不是 voice，按渠道关就把它的 cues 也砍了；文字端本来就不读这个键。
        if raw != chunk:
            data["raw_delta"] = raw
        # 正文追加与事件发布合成一次 Redis 往返：这两件事永远一起发生，
        # 分开写就是每帧 4 条串行命令。托管 Redis 单命令 193 ms，27 帧差 30 多秒。
        # 落进 turn:{tid}:text 的也是清洗后的 chunk——SSE 重连的 turn.snapshot 直接发它。
        await self._control.publish_and_append(
            session_id=inp.session_id, turn_id=inp.turn_id, event="message.delta",
            data=data, delta=chunk)

    # ---- 控制流 ----

    async def _absorb(self, inp: TurnInput, state: _RunState, inbox: SteerInbox,
                      entries: list[tuple[str, dict[str, str]]]) -> None:
        """处理控制消息。按 id 去重：同步读取与后台读取可能看到同一条。"""
        for entry_id, fields in entries:
            if not _id_after(entry_id, state.ctl_last):
                continue
            state.ctl_last = entry_id
            kind = fields.get("kind")
            message_id = int(fields.get("message_id", "0") or 0)
            text = fields.get("text", "")
            if kind == "merge":
                if state.output_started:
                    # 已经开始输出（不应发生：Lua 不会在 output 阶段合并）：改为排队，不丢输入。
                    await self._requeue(inp, message_id, text)
                else:
                    state.merge_requested = True
                    state.merged.append((message_id, text))
            elif kind == "steer":
                inbox.push(str(message_id), text)
                state.steer_pushed.append(message_id)
            elif kind == "cancel":
                state.cancelled = True

    async def _watch_ctl(self, inp: TurnInput, inbox: SteerInbox, state: _RunState, stop: asyncio.Event) -> None:
        while not stop.is_set():
            entries = await self._control.read_ctl(turn_id=inp.turn_id, last_id=state.ctl_last, block_ms=500)
            await self._absorb(inp, state, inbox, entries)

    async def _renew(self, inp: TurnInput, state: _RunState, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await asyncio.sleep(LOCK_RENEW_SEC)
            if not await self._control.renew_lock(session_id=inp.session_id, owner=inp.owner):
                log.error("lock lost", extra={"turn_id": inp.turn_id})
                state.lost = True   # 主循环在下一个事件处停止产出
                stop.set()
                return

    async def _requeue(self, inp: TurnInput, message_id: int, text: str) -> None:
        if not message_id or not text:
            return
        item = await self._queue.enqueue(owner_id=inp.owner_id, session_id=inp.session_id,
                                         message_id=message_id, client_message_id=None, text=text)
        await self._control.publish(session_id=inp.session_id, event="input.queued",
                                    data={"message_id": message_id, "queue_position": item.id})

    async def _attach_merged(self, inp: TurnInput, state: _RunState) -> None:
        # input.merged 由提交方发出（提交时即时反馈）；这里只负责挂接，不重复发事件。
        ids = [message_id for message_id, _ in state.merged]
        await self._messages.attach_turn(owner_id=inp.owner_id, session_id=inp.session_id,
                                         message_ids=ids, turn_id=inp.turn_id)

    # ---- 收尾 ----

    async def _finish(self, inp: TurnInput, state: _RunState, inbox: SteerInbox, failed: bool = False) -> None:
        """收尾入口：尽力而为，绝不把异常抛穿给 ``_run`` 的 finally。

        2026-11-28 生产挂死的第二条腿：旧写法里 ``finally: await self._finish(...)``
        没有任何保护，收尾里任何一步抛错（flush 撞 Redis、DB append、attach_turn……）
        → **终止事件和放锁一起丢**，表现与「回合永不终结」完全相同。现在：
        - ``_finish_body`` 内部关键步骤各自 try/except（旁路失败只记日志）；
        - 事件+放锁（``finish_turn``）失败 → ``_finish_emergency``：终止事件与
          ``release_lock`` 分开各自再试一次（一次 Redis 往返失败不该拖累另一件事）；
        - ``state.closed`` 记录「终止事件或放锁至少已尝试成功」，避免紧急路径重复补刀。
        """
        if state.lost:
            try:
                await self._finish_lost(inp, state)
            except Exception:  # noqa: BLE001
                log.exception("turn finish(lost) failed", extra={"turn_id": inp.turn_id})
            if not state.closed:
                await self._finish_emergency(inp, state)
            return
        try:
            await self._finish_body(inp, state, inbox, failed=failed)
        except Exception:  # noqa: BLE001 —— 收尾失败不许吞掉「终止事件 + 放锁」这两件保底事
            log.exception("turn finish failed", extra={"turn_id": inp.turn_id})
        if not state.closed:
            await self._finish_emergency(inp, state)

    async def _finish_emergency(self, inp: TurnInput, state: _RunState) -> None:
        """保底：正常收尾没走到「事件+放锁」，两件事分开各自尽力一次。

        发终止事件与放锁互为独立尝试——Redis 此刻可能完全不可用，也可能只是 DB 挂了；
        无论哪种，都不许出现「锁还活着、SSE 永远等不到结束」的组合。
        """
        log.error("turn finishing via emergency path", extra={"turn_id": inp.turn_id})
        try:
            await self._control.publish(session_id=inp.session_id, event="error",
                                        data={"turn_id": inp.turn_id, "code": "turn_failed",
                                              "message": "回答中断，请重试", "retryable": True})
        except Exception:  # noqa: BLE001
            log.exception("emergency error publish failed", extra={"turn_id": inp.turn_id})
        try:
            await self._control.release_lock(session_id=inp.session_id, owner=inp.owner)
            state.closed = True
        except Exception:  # noqa: BLE001 —— 最后的兜底是锁 TTL 与恢复流程（turn_recovery）
            log.exception("emergency release_lock failed", extra={"turn_id": inp.turn_id})

    async def _finish_body(self, inp: TurnInput, state: _RunState, inbox: SteerInbox, failed: bool = False) -> None:
        try:
            await self._flush(inp, state)
        except Exception:  # noqa: BLE001 —— 残余帧发不出去不改变回合结局，正文仍按 deltas 落库
            log.exception("finish flush failed", extra={"turn_id": inp.turn_id})
        full = "".join(state.deltas)
        interrupted = state.cancelled or failed
        # 打断前缀（契约 v2 §2.2）：房间 worker 在 barge 时把端侧 played_ms 折算成
        # 字符数写进 turn:{tid}:prefix；这里只在取消的回合读一次。读不到就是 0，
        # 线程补记退回全量——退回旧行为比按一个不可信的估计截断更安全。
        prefix_chars = 0
        if state.cancelled and self._control is not None:
            reader = getattr(self._control, "read_spoken_prefix", None)
            if reader is not None:
                try:
                    prefix_chars = int(await reader(turn_id=inp.turn_id))
                except Exception:  # noqa: BLE001 —— 前缀是旁路，读失败不改变回合结局
                    prefix_chars = 0
        prefix_text = full[:prefix_chars] if prefix_chars > 0 else ""
        saved_id: int | None = None
        saved_alt_group: int | None = None
        append_failed = False
        # 落库条件只看「有没有说过话」，不看是否被取消（取证 2026-11-26：空 AI 气泡的根因）。
        # 原先是 `full or interrupted`：取消且一字未收时会写下一条 content="" 的 assistant 行
        # （interrupted=True），客户端兜底拉历史就把它带回成「只有头像的空气泡」，而对着空行
        # 点「继续」也毫无意义。口径与非取消的空 completion 一致（见下面的 empty_completion 分支）：
        # 她没说什么，就不该作为一条回复进历史喂模型。有半截正文的打断照旧存、照旧标记；
        # 失败（failed）回合维持原行为——它的空行是 turn_failed 收尾的一部分，不在本次范围。
        if full or (failed and not state.cancelled):
            meta: dict[str, Any] = {"lc_ids": list(state.lc_ids)} if state.lc_ids else {}
            if prefix_chars > 0:
                # content 仍存全量（不丢信息）；前缀只进 meta，无需新列（基线守卫不受影响）。
                meta["spoken_prefix_chars"] = prefix_chars
            try:
                saved = await self._messages.append(
                    owner_id=inp.owner_id, session_id=inp.session_id, role="assistant", content=full,
                    kind="chat", client_message_id=None, turn_id=inp.turn_id,
                    meta=meta, fence=inp.fence,
                    **({"alt_of": inp.alt_of} if inp.alt_of is not None else {}))
            except Exception:  # noqa: BLE001 —— 落库抛错：没有回复可「完成」，回合改按 error 收尾（见下）
                log.exception("finish append failed", extra={"turn_id": inp.turn_id})
                append_failed = True
                saved = None
            if saved is None and not append_failed:
                # 围栏号已不是最新：这把锁过期后被别的进程接手过。不写、不发完成事件。
                state.lost = True
                await self._finish_lost(inp, state)
                return
            if not append_failed:
                saved_id = saved.id
                saved_alt_group = saved.alt_group
                if interrupted:
                    try:
                        await self._messages.mark_interrupted(owner_id=inp.owner_id, message_id=saved.id)
                    except Exception:  # noqa: BLE001 —— 标记失败不改变回合结局
                        log.exception("finish mark_interrupted failed", extra={"turn_id": inp.turn_id})

        # 插话：被注入的挂到回合上；没被注入的转回队列（D §6.4），不丢。
        # 这两步是记账旁路：抛错只记日志——回复已经落库，不能因为挂接失败把整个
        # 收尾降级成 error（终止事件+放锁优先于记账完整）。
        remaining = inbox.remaining()
        remaining_ids = {int(mid) for mid, _ in remaining}
        injected = [mid for mid in state.steer_pushed if mid not in remaining_ids]
        try:
            await self._messages.attach_turn(owner_id=inp.owner_id, session_id=inp.session_id,
                                             message_ids=injected, turn_id=inp.turn_id)
        except Exception:  # noqa: BLE001
            log.exception("finish attach_turn failed", extra={"turn_id": inp.turn_id})
        for mid, text in remaining:
            try:
                await self._requeue(inp, int(mid), text)
            except Exception:  # noqa: BLE001
                log.exception("finish requeue failed", extra={"turn_id": inp.turn_id,
                                                              "message_id": mid})

        await self._notify(inp, state, saved_id=saved_id, text=full, interrupted=interrupted,
                           failed=failed, spoken_prefix=prefix_text)
        # 收尾的最后一个事件、删回合状态、放锁，合成一次 Redis 往返。
        # 顺序有硬约束（事件先发、状态在放锁之前删），pipeline 按注册顺序执行所以不变。
        if append_failed:
            # 回复没落库：不能报完成。error 事件仍走 finish_turn——事件、清回合状态、
            # 放锁仍是同一次原子往返，比 publish+release_lock 拆开的紧急路径更干净。
            await self._control.finish_turn(session_id=inp.session_id, owner=inp.owner,
                                            turn_id=inp.turn_id, event="error",
                                            data={"turn_id": inp.turn_id, "code": "turn_failed",
                                                  "message": "回答中断，请重试", "retryable": True})
            state.closed = True
        elif saved_id is not None or state.cancelled:
            event = "message.done" if saved_id is not None else "turn.cancelled"
            data: dict[str, Any] = {"turn_id": inp.turn_id, "assistant_message_id": saved_id}
            if saved_id is not None:
                data.update({"steered_message_ids": injected, "usage": None})
                if saved_alt_group is not None:
                    data["alt_group"] = saved_alt_group
            await self._control.finish_turn(session_id=inp.session_id, owner=inp.owner,
                                            turn_id=inp.turn_id, event=event, data=data)
            state.closed = True
        else:
            # 跑完整个回合、一个可见 token 都没有（provider 空 completion）。过去这里
            # 只清状态不放事件：订阅这条回合的语音 tokens() 等不到 END 事件，只能熬满
            # 120 秒超时（生产 voice.log 里 `voice turn timed out … mode=merged` 就是它），
            # 文字端「正在输入」也不会停。发可重试的 error 让两端立即收流；空的 assistant
            # 消息仍不存——它没说什么，不该作为一条空回复进历史喂模型。
            log.warning("turn produced no output", extra={"turn_id": inp.turn_id})
            await self._control.finish_turn(session_id=inp.session_id, owner=inp.owner,
                                            turn_id=inp.turn_id, event="error",
                                            data={"turn_id": inp.turn_id, "code": "empty_completion",
                                                  "message": "没有生成回答，请重试", "retryable": True})
            state.closed = True
        if self._drain is not None and not failed:
            await self._drain(owner_id=inp.owner_id, session_id=inp.session_id,
                              character_id=inp.character_id)

    async def _finish_lost(self, inp: TurnInput, state: _RunState) -> None:
        """锁已不是我们的：不写回复、不清回合状态、不排空（这些都属于接手的那个进程）。

        每一步单独尽力：publish 抛错不能挡住 release_lock（条件放锁，只删自己的）。
        """
        try:
            await self._control.publish(session_id=inp.session_id, event="error",
                                        data={"turn_id": inp.turn_id, "code": "turn_failed",
                                              "message": "回答中断，请重试", "retryable": True})
        except Exception:  # noqa: BLE001
            log.exception("finish_lost error publish failed", extra={"turn_id": inp.turn_id})
        await self._notify(inp, state, saved_id=None, text="", interrupted=True, failed=True)
        try:
            await self._control.release_lock(session_id=inp.session_id, owner=inp.owner)  # 只释放自己的
            state.closed = True
        except Exception:  # noqa: BLE001
            log.exception("finish_lost release_lock failed", extra={"turn_id": inp.turn_id})

    async def _notify(self, inp: TurnInput, state: _RunState, *, saved_id: int | None, text: str,
                      interrupted: bool, failed: bool, spoken_prefix: str = "") -> None:
        # 指标写在 after_turn 判断**之前**：after_turn 只在组合根装了收尾钩子时才有，
        # 拿它当开关会让这条指标在某些部署里静默消失，而回合的结局是任何部署都要看到的。
        ended = time.monotonic()
        verdict = "lost" if state.lost else "failed" if failed else \
            "cancelled" if state.cancelled else "interrupted" if interrupted else "done"
        metrics.observe_turn(
            state=verdict, duration_sec=ended - state.started,
            ttft_sec=(state.first_output_at - state.started) if state.first_output_at else None,
            role=inp.character_id or "chat")
        if self._after_turn is None:
            return
        user_ids = tuple(inp.message_ids) + tuple(mid for mid, _ in state.merged)
        outcome = TurnOutcome(
            owner_id=inp.owner_id, session_id=inp.session_id, character_id=inp.character_id,
            turn_id=inp.turn_id, user_message_ids=user_ids, user_text=inp.text,
            assistant_message_id=saved_id, assistant_text=text, interrupted=interrupted,
            cancelled=state.cancelled, failed=failed, lock_lost=state.lost, lc_ids=tuple(state.lc_ids),
            spoken_prefix=spoken_prefix)
        try:
            await self._after_turn(outcome)
        except Exception:  # noqa: BLE001 —— 收尾钩子失败不影响回合结果
            log.exception("after_turn failed", extra={"turn_id": inp.turn_id})
