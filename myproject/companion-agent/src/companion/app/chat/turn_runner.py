"""回合执行（D §6.2–6.5、§7.3）。

一个回合 = 一把锁 + 一个 turn_id。本进程负责：
- 续租锁（每 10 秒）；
- 读取 turn:{tid}:ctl：merge 在首个可见 token 之前中止并用同一 turn_id 重跑；
  steer 进收件箱；cancel 中止；
- 维护 phase（pre_output → output → tool），只前进不回退；
- 把回合覆盖的用户消息挂到回合上（attach_turn，见 D §3.3）：启动时的消息、合并进来的、
  实际被注入的插话；未被注入的插话与无法合并的输入转回队列，不挂接；
- 增量合并写 message.delta（50 毫秒或 64 字符一次），正文另存 turn:{tid}:text；
- 结束时落库助手消息、释放锁、尝试排空。

produce 由 bootstrap 注入（把 DeerFlow 的事件流接进来），这里不认识 LangGraph。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

from companion.app.chat.lifecycle import DrainState
from companion.domain.turn.queue import TurnPhase
from companion.domain.turn.steer import SteerInbox
from companion.ports.brain import BrainEvent, TextDelta, ToolFinished, ToolStarted, TurnRequest
from companion.ports.store import MessageStore, QueueStore
from companion.ports.turn_control import TurnControlPort

log = logging.getLogger("companion.turn")

LOCK_RENEW_SEC = 10.0
DELTA_FLUSH_SEC = 0.05
DELTA_FLUSH_CHARS = 64
MAX_RESTARTS = 2

Produce = Callable[[TurnRequest, SteerInbox], AsyncIterator[BrainEvent]]
Drain = Callable[..., Awaitable[None]]


@dataclass
class TurnInput:
    owner_id: int
    session_id: int
    character_id: str
    turn_id: str
    owner: str                 # 锁持有者，形如 "{process}:{turn_id}"
    text: str
    message_ids: list[int]     # 启动时覆盖的用户消息（排空时可能有多条）


@dataclass
class _RunState:
    merge_requested: bool = False
    merged: list[tuple[int, str]] = field(default_factory=list)
    steer_pushed: list[int] = field(default_factory=list)
    cancelled: bool = False
    output_started: bool = False
    deltas: list[str] = field(default_factory=list)
    pending: str = ""
    last_flush: float = field(default_factory=time.monotonic)

    def restart(self) -> None:
        self.merge_requested = False
        self.merged = []
        self.output_started = False
        self.deltas = []
        self.pending = ""
        self.last_flush = time.monotonic()


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
    ) -> None:
        self._control = control
        self._messages = messages
        self._queue = queue
        self._produce = produce
        self._drain = drain
        self._tracker = tracker
        self._steer_budget = steer_budget

    async def run(self, inp: TurnInput) -> None:
        if self._tracker is not None:
            self._tracker.turn_started()
        try:
            await self._run(inp)
        finally:
            if self._tracker is not None:
                self._tracker.turn_finished()

    async def _run(self, inp: TurnInput) -> None:
        state = _RunState()
        inbox = SteerInbox(budget=self._steer_budget)
        texts = [inp.text]
        restarts = 0
        stop = asyncio.Event()
        renew = asyncio.create_task(self._renew(inp, stop))
        watch = asyncio.create_task(self._watch_ctl(inp, inbox, state, stop))
        failed = False
        try:
            await self._messages.attach_turn(owner_id=inp.owner_id, session_id=inp.session_id,
                                             message_ids=inp.message_ids, turn_id=inp.turn_id)
            await self._control.publish(session_id=inp.session_id, event="turn.started",
                                        data={"turn_id": inp.turn_id, "user_message_ids": inp.message_ids})
            while True:
                outcome = await self._attempt(inp, texts, inbox, state)
                if outcome != "merged":
                    break
                if restarts >= MAX_RESTARTS:
                    # 重跑次数用尽：合并进来的输入不能再进这个回合，改为排队（D §6.3）。
                    for message_id, text in state.merged:
                        await self._requeue(inp, message_id, text)
                    break
                restarts += 1
                await self._attach_merged(inp, state)
                texts = texts + [text for _mid, text in state.merged]
                state.restart()  # 原地重置：控制协程持有的是同一个对象（首 token 前合并，无可见内容需撤回）
                await self._control.publish(session_id=inp.session_id, event="turn.restarted",
                                            data={"turn_id": inp.turn_id,
                                                  "user_message_ids": inp.message_ids + [m for m, _ in state.merged]})
        except Exception:
            log.exception("turn failed", extra={"turn_id": inp.turn_id})
            failed = True
            await self._control.publish(session_id=inp.session_id, event="error",
                                        data={"turn_id": inp.turn_id, "code": "turn_failed",
                                              "message": "回答中断，请重试", "retryable": True})
        finally:
            stop.set()
            for task in (renew, watch):
                task.cancel()
            await asyncio.gather(renew, watch, return_exceptions=True)
            # 收尾只执行一次：无论成功、失败，锁都必须释放。
            await self._finish(inp, state, inbox, failed=failed)

    # ---- 一次模型调用 ----

    async def _attempt(self, inp: TurnInput, texts: list[str], inbox: SteerInbox, state: _RunState) -> str:
        request = TurnRequest(user_id=str(inp.owner_id), character_id=inp.character_id,
                              message="\n\n".join(texts), thread_id=inp.turn_id)
        stream = self._produce(request, inbox)
        try:
            async for event in stream:
                if state.cancelled:
                    return "cancelled"
                if state.merge_requested and not state.output_started:
                    return "merged"
                if isinstance(event, TextDelta):
                    await self._on_text(inp, state, event.text)
                elif isinstance(event, ToolStarted):
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

    async def _on_text(self, inp: TurnInput, state: _RunState, text: str) -> None:
        if not state.output_started:
            state.output_started = True
            await self._control.advance_phase(session_id=inp.session_id, phase=TurnPhase.OUTPUT)
        state.deltas.append(text)
        state.pending += text
        now = time.monotonic()
        if len(state.pending) >= DELTA_FLUSH_CHARS or now - state.last_flush >= DELTA_FLUSH_SEC:
            await self._flush(inp, state)

    async def _flush(self, inp: TurnInput, state: _RunState) -> None:
        if not state.pending:
            return
        chunk, state.pending = state.pending, ""
        state.last_flush = time.monotonic()
        await self._control.append_text(turn_id=inp.turn_id, delta=chunk)
        await self._control.publish(session_id=inp.session_id, event="message.delta",
                                    data={"turn_id": inp.turn_id, "delta": chunk})

    # ---- 控制流 ----

    async def _watch_ctl(self, inp: TurnInput, inbox: SteerInbox, state: _RunState, stop: asyncio.Event) -> None:
        last = "0-0"
        while not stop.is_set():
            for entry_id, fields in await self._control.read_ctl(turn_id=inp.turn_id, last_id=last, block_ms=500):
                last = entry_id
                kind = fields.get("kind")
                message_id = int(fields.get("message_id", "0") or 0)
                text = fields.get("text", "")
                if kind == "merge":
                    if state.output_started:
                        # Lua 与首 token 之间的竞态：已经开始输出，不能再合并。改为排队。
                        await self._requeue(inp, message_id, text)
                    else:
                        state.merge_requested = True
                        state.merged.append((message_id, text))
                elif kind == "steer":
                    inbox.push(str(message_id), text)
                    state.steer_pushed.append(message_id)
                elif kind == "cancel":
                    state.cancelled = True

    async def _renew(self, inp: TurnInput, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await asyncio.sleep(LOCK_RENEW_SEC)
            if not await self._control.renew_lock(session_id=inp.session_id, owner=inp.owner):
                log.error("lock lost", extra={"turn_id": inp.turn_id})
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
        ids = [message_id for message_id, _ in state.merged]
        # input.merged 由提交方发出（提交时即时反馈）；这里只负责挂接，不重复发事件。
        await self._messages.attach_turn(owner_id=inp.owner_id, session_id=inp.session_id,
                                         message_ids=ids, turn_id=inp.turn_id)

    # ---- 收尾 ----

    async def _finish(self, inp: TurnInput, state: _RunState, inbox: SteerInbox, failed: bool = False) -> None:
        await self._flush(inp, state)
        full = "".join(state.deltas)
        interrupted = state.cancelled or failed
        saved_id: int | None = None
        if full or interrupted:
            saved = await self._messages.append(
                owner_id=inp.owner_id, session_id=inp.session_id, role="assistant", content=full,
                kind="chat", client_message_id=None, turn_id=inp.turn_id, meta={})
            saved_id = saved.id
            if interrupted:
                await self._messages.mark_interrupted(owner_id=inp.owner_id, message_id=saved.id)

        # 插话：被注入的挂到回合上；没被注入的转回队列（D §6.4），不丢。
        remaining = inbox.remaining()
        remaining_ids = {int(mid) for mid, _ in remaining}
        injected = [mid for mid in state.steer_pushed if mid not in remaining_ids]
        await self._messages.attach_turn(owner_id=inp.owner_id, session_id=inp.session_id,
                                         message_ids=injected, turn_id=inp.turn_id)
        for mid, text in remaining:
            await self._requeue(inp, int(mid), text)

        if saved_id is not None:
            await self._control.publish(
                session_id=inp.session_id, event="message.done",
                data={"turn_id": inp.turn_id, "assistant_message_id": saved_id,
                      "steered_message_ids": injected, "usage": None})
        if state.cancelled:
            await self._control.publish(session_id=inp.session_id, event="turn.cancelled",
                                        data={"turn_id": inp.turn_id, "assistant_message_id": saved_id})

        await self._control.clear_turn(session_id=inp.session_id)
        await self._control.release_lock(session_id=inp.session_id, owner=inp.owner)
        if self._drain is not None and not failed:
            await self._drain(owner_id=inp.owner_id, session_id=inp.session_id,
                              character_id=inp.character_id)
