"""语音回合的大脑：不自己跑模型，而是把话交给文字聊天同一条提交路径。

原来的语音链路是 ``TurnPipeline`` 直连大脑：说的话不落库、不拿会话锁、没有对话线程、
不触发 ``after_turn``（记忆、画像、时间线）。同一个用户在同一个会话里，文字和语音
成了两份互不相干的历史。

这里换成：语音识别出的文字走 ``SubmitService.submit``（与文字输入框完全相同），回合由
``TurnRunner`` 执行并落库；本类只负责把这一回合的 ``message.delta`` 事件当作 token 流
交还给 ``TurnPipeline``，由它断句、剥情绪标签、交给 TTS。这样断句与打断逻辑不变，
变的只有“文字从哪来”：从回合事件流，而不是直连大脑。

会话忙时（MERGED / QUEUED）也不能返回空流：文字侧 drain 之后仍会产出回复，语音
必须挂等并朗读那一轮，否则端上就是 ``said=''`` / remote PCM=0。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from companion.service.turn.queue import Disposition
from companion.agent.brain.port import BrainTurn, TurnRefused, TurnRequest

logger = logging.getLogger(__name__)

# 一个回合从提交到结束的上限。到了就收尾，不让房间一直静音等一个已经卡死的回合。
DEFAULT_TURN_TIMEOUT_SEC = 120.0
_POLL_MS = 1000
_END_EVENTS = frozenset({"message.done", "turn.cancelled", "error"})

#: 并入 submit 的附件条目 kind。``control.input`` 这一路只承载图片，而 ``submit`` 把它
#: 原样存进 ``meta["attachments"]``、读 API 原样带回，客户端解析以这个拼写为准。
_ATTACHMENT_KIND = "image"


class PlatformBrain:
    """``BrainPort`` 的实现：提交到平台，读回同一回合的文字流。"""

    def __init__(self, *, submit: Any, control: Any, turn_timeout_sec: float = DEFAULT_TURN_TIMEOUT_SEC,
                 role: str = "user", kind: str = "voice",
                 wait_for_busy: bool = True, pending_attachments: Any = None) -> None:
        """``role`` / ``kind`` 是这条输入在历史里的身份：语音是 user/voice；
        服务端主动开口是 system/proactive（模型看到的是一条带标记的指令，不是用户说的话）。

        ``wait_for_busy``：语音为 True——会话忙（QUEUED/MERGED）时挂等 drain / 跟活跃回合，
        否则端上就是 ``said=''``；主动开口为 False——忙就返回空串，由循环按 empty_turn 跳过，
        真正朗读留给语音或用户下次打开对话。

        ``pending_attachments``：端侧那条带图消息的 ``upload_ids`` 暂存位
        （``api.livekit.input_attachments.PendingAttachmentSlot``，形状：``consume() ->
        list[str]``）。数据通道上的 attachments 事件和 lk.chat 上的文字是两条独立通道，
        顺序不保证，所以只能在这里（提交前最后一站）合并。不传就是纯文本回合——后台主动
        开口（``service/jobs/background.py``）根本没有附件可来。"""
        self._submit = submit
        self._control = control
        self._timeout = turn_timeout_sec
        self._role = role
        self._kind = kind
        self._wait_for_busy = wait_for_busy
        self._pending = pending_attachments

    def _take_attachments(self) -> list[dict[str, Any]] | None:
        """从暂存位取走本回合的附件，换成 ``submit`` 认识的条目形状。

        取走即清（槽的语义），所以一批附件只会落进一条消息。空槽返回 ``None`` 而不是
        ``[]``：``submit`` 里 ``if attachments:`` 两种都当没有，但 ``None`` 让它和
        「这条消息压根不带附件」在 meta 里长得一模一样，历史接口不会多出空数组。
        """
        if self._pending is None:
            return None
        try:
            upload_ids = self._pending.consume()
        except Exception as exc:  # noqa: BLE001 —— 附件读失败不该让整句话提交不了
            logger.warning("pending attachments consume failed: %s", exc)
            return None
        if not upload_ids:
            return None
        logger.info("merging %d pending attachment(s) into this turn", len(upload_ids))
        return [{"upload_id": upload_id, "kind": _ATTACHMENT_KIND} for upload_id in upload_ids]

    async def start_turn(self, request: TurnRequest) -> BrainTurn:
        if request.session_id is None:
            # 没有会话就没有历史可共享：这是装配错误，不是运行时可以绕过的情况
            raise ValueError("voice turn needs a chat session id")
        try:
            owner_id = int(request.user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"user id must be numeric, got {request.user_id!r}") from exc

        # 先记游标再提交：回合可能在 submit 返回前就开始吐字，晚记会漏掉开头几个字
        cursor = await self._control.tail_event_id(session_id=request.session_id)
        # 附件在 submit 前最后一刻才取：取早了， attachments 事件还在路上，
        # 一条带图消息就变成了纯文本；取晚了没有意义，文字和图必须在同一条消息里。
        attachments = self._take_attachments()
        result = await self._submit.submit(
            owner_id=owner_id, session_id=request.session_id, character_id=request.character_id,
            text=request.message, client_message_id=None,
            # 语音一次一句，用户说完才提交；不做“插话进正在跑的回合”
            steerable=False,
            # 来源标记：转写文字和打字的区别在这里，质检与记忆降置信度都靠它
            role=self._role, kind=self._kind,
            # 端侧 control.input(kind=attachments) 暂存下来的图；None 表示这条没图
            attachments=attachments)

        if result.status == "denied":
            raise TurnRefused(getattr(result, "reason", None))
        if result.status == "duplicate":
            # 幂等命中：没有新回合可播，保持静音比复读旧回复更安全。
            logger.info("voice turn duplicate message_id=%s", getattr(result, "message_id", None))
            return BrainTurn(tokens=_empty(), cancel=_noop, turn_id=result.turn_id or "",
                             user_message_id=getattr(result, "message_id", None))
        if result.status != "accepted":
            logger.info("voice turn not accepted status=%s", result.status)
            return BrainTurn(tokens=_empty(), cancel=_noop, turn_id=result.turn_id or "",
                             user_message_id=getattr(result, "message_id", None))

        message_id = getattr(result, "message_id", None)
        disposition = result.disposition
        known_turn_id = result.turn_id or ""
        control, session_id, timeout = self._control, request.session_id, self._timeout

        if disposition is Disposition.STARTED and known_turn_id:
            bind_mode = "started"
        elif not self._wait_for_busy:
            # 主动开口：忙就空返回，不占着循环等 drain。
            logger.info("proactive turn not started disposition=%s", disposition)
            return BrainTurn(tokens=_empty(), cancel=_noop, turn_id=known_turn_id,
                             user_message_id=message_id)
        elif disposition is Disposition.MERGED and known_turn_id:
            # 合并进正在跑的回合：直接订阅那个 turn_id。
            bind_mode = "merged"
            logger.info("voice turn merged into turn=%s message_id=%s", known_turn_id, message_id)
        elif disposition is Disposition.QUEUED:
            # 排队：等 drain 发出 turn.started(user_message_ids 含本条) 再订阅。
            bind_mode = "queued"
            logger.info("voice turn queued message_id=%s; waiting for drain", message_id)
        elif disposition is Disposition.STEERED and known_turn_id:
            # 语音提交 steerable=False，正常不会走到这里；有 turn_id 就跟过去。
            bind_mode = "steered"
            logger.info("voice turn steered into turn=%s message_id=%s", known_turn_id, message_id)
        else:
            logger.info("voice turn unsupported disposition=%s turn_id=%r", disposition, known_turn_id)
            return BrainTurn(tokens=_empty(), cancel=_noop, turn_id=known_turn_id,
                             user_message_id=message_id)

        # QUEUED 时 turn_id 要等 drain；BrainTurn 是可变 dataclass，tokens 绑定后就地写回。
        turn = BrainTurn(tokens=_empty(), cancel=_noop,
                         turn_id=known_turn_id if bind_mode != "queued" else "",
                         user_message_id=message_id)

        async def tokens() -> AsyncIterator[str]:
            deadline = time.monotonic() + timeout
            after = cursor
            turn_id = turn.turn_id
            started = time.monotonic()
            deltas = 0
            first_logged = False
            while time.monotonic() < deadline:
                events = await control.wait_events(session_id=session_id, after_id=after, block_ms=_POLL_MS)
                for entry_id, name, data in events:
                    after = entry_id
                    if not turn_id:
                        if name != "turn.started":
                            continue
                        ids = data.get("user_message_ids") or []
                        try:
                            matched = message_id is not None and int(message_id) in {int(x) for x in ids}
                        except (TypeError, ValueError):
                            matched = False
                        if not matched:
                            continue
                        turn_id = str(data.get("turn_id") or "")
                        if not turn_id:
                            continue
                        turn.turn_id = turn_id
                        logger.info("voice turn drained turn=%s message_id=%s", turn_id, message_id)
                        continue
                    if data.get("turn_id") != turn_id:
                        continue
                    if name == "message.delta":
                        # 优先 raw_delta：TurnRunner 落库/发布的是剥掉协议片段的展示文本，
                        # cues 只在原文里，TTS 链路必须读原文（没有 raw_delta 就是两串一致）。
                        delta = data.get("raw_delta") or data.get("delta")
                        if delta:
                            deltas += 1
                            if not first_logged:
                                # ② 段收口：voice 侧看到首 delta 的时刻（不是模型侧）——
                                # 首句 19–31 秒里，chat 发进事件流慢和 voice 断句慢在这行两侧分开。
                                first_logged = True
                                logger.info("voice turn first delta turn=%s after_ms=%d",
                                            turn_id, int((time.monotonic() - started) * 1000))
                            yield str(delta)
                    elif name in _END_EVENTS:
                        # 收流原因 + 喂了多少 delta：`said=''` 但 `interrupted=False` 时，
                        # 这行分清 token 是丢在回合之前（deltas=0）还是断句之后（deltas>0）。
                        logger.info("voice turn stream end turn=%s message_id=%s mode=%s event=%s deltas=%d",
                                    turn_id, message_id, bind_mode, name, deltas)
                        return
            logger.warning("voice turn timed out turn=%s message_id=%s mode=%s",
                           turn.turn_id or "", message_id, bind_mode)

        async def cancel() -> None:
            if turn.turn_id:
                # 取消的是共享的文字回合：别的语音订阅者（merged/queued 挂同一 turn）
                # 会因此提前收流，没这行就对不上是谁杀的。
                logger.info("voice turn cancel sent turn=%s message_id=%s", turn.turn_id, message_id)
                await control.send_cancel(turn_id=turn.turn_id)

        turn.tokens = tokens()
        turn.cancel = cancel
        return turn

    async def aclose(self) -> None:
        # 提交服务与控制面由 platform 持有并关闭
        return None


async def _empty() -> AsyncIterator[str]:
    return
    yield ""  # pragma: no cover  让它成为异步生成器


async def _noop() -> None:
    await asyncio.sleep(0)
