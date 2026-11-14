"""提交与重跑（D §6.1、§6.6、A §5.1）。

提交顺序固定：幂等 → 安全检测 → 落库 → Redis 原子判定 → 按处置执行。
安全检测对每条输入都执行，包括之后会被合并、插话或排队的输入（T §1、M11）。
重跑（重新生成、继续、重试）不经过判定：它只能在会话空闲时开始，否则返回忙。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from companion.agent.util.ids import new_ulid
from companion.agent.middleware.safety import check_input
from companion.service.turn.queue import Disposition
from companion.db.port import MessageStore, QueueStore, SessionStore
from companion.service.turn.control import TurnControlPort

# 启动一个回合的回调（由 bootstrap 注入，内部把 TurnRunner 放到后台任务里跑）。
StartTurn = Callable[..., Awaitable[None]]

LOCK_RETRIES = 3


@dataclass(frozen=True)
class SubmitResult:
    status: str                        # accepted | duplicate | denied
    disposition: Disposition | None    # accepted 时有值
    message_id: int
    turn_id: str | None
    reason: str | None = None


class SubmitService:
    def __init__(
        self,
        *,
        messages: MessageStore,
        queue: QueueStore,
        control: TurnControlPort,
        start_turn: StartTurn,
        steer_budget: int = 3,
        max_restarts: int = 2,
        process_name: str | None = None,
        sessions: SessionStore | None = None,
    ) -> None:
        self._messages = messages
        self._sessions = sessions
        self._queue = queue
        self._control = control
        self._start_turn = start_turn
        self._steer_budget = steer_budget
        self._max_restarts = max_restarts
        self._process = process_name or f"pid{os.getpid()}"

    @property
    def process_name(self) -> str:
        return self._process

    async def submit(self, *, owner_id: int, session_id: int, character_id: str, text: str,
                     client_message_id: str | None, steerable: bool = True, role: str = "user",
                     kind: str = "chat", attachments: list[dict[str, Any]] | None = None) -> SubmitResult:
        """``role`` / ``kind``：用户消息是 user/chat；服务端发起的主动回合（到点提醒）是 system/proactive，
        走同一条判定路径（会话忙时排队），模型看到的是一条带标记的指令。"""
        if client_message_id:
            existing = await self._messages.find_by_client_id(
                owner_id=owner_id, session_id=session_id, client_message_id=client_message_id)
            if existing is not None:
                return SubmitResult("duplicate", None, existing.id, existing.turn_id)

        denied = check_input(text)
        if denied is not None:
            return SubmitResult("denied", None, 0, None, reason=denied)

        # 附件（图片/文件）跟着这条用户消息一起存进 meta：一个上传只属于一条消息，
        # 单独建表反而要额外维护「哪条消息引用哪个上传」的关系。
        meta: dict[str, Any] = {"attachments": list(attachments)} if attachments else {}
        message = await self._messages.append(
            owner_id=owner_id, session_id=session_id, role=role, content=text, kind=kind,
            client_message_id=client_message_id, turn_id=None, meta=meta)
        await self._control.publish(
            session_id=session_id, event="message.created",
            data={"message_id": message.id, "client_message_id": client_message_id, "role": role,
                  "kind": kind, "content": text, "created_at": message.created_at.isoformat()})

        for _ in range(LOCK_RETRIES):
            disposition, turn_id = await self._control.decide(
                session_id=session_id, message_id=str(message.id), text=text, steerable=steerable,
                steer_budget=self._steer_budget, max_restarts=self._max_restarts)

            if disposition is Disposition.STARTED:
                started = await self._start(owner_id=owner_id, session_id=session_id,
                                            character_id=character_id, text=text, message_ids=[message.id])
                if started is not None:
                    return SubmitResult("accepted", Disposition.STARTED, message.id, started)
                continue  # 别的请求刚抢到锁：回到判定，这次大概率是合并/插话/排队

            if disposition in (Disposition.MERGED, Disposition.STEERED):
                # 控制消息已由 Lua 原子写入 turn:{tid}:ctl；回合进程会接手并挂接消息。
                event = "input.merged" if disposition is Disposition.MERGED else "input.steered"
                await self._control.publish(session_id=session_id, event=event,
                                            data={"message_id": message.id, "turn_id": turn_id})
                return SubmitResult("accepted", disposition, message.id, turn_id)

            item = await self._queue.enqueue(
                owner_id=owner_id, session_id=session_id, message_id=message.id,
                client_message_id=client_message_id, text=text)
            await self._control.publish(session_id=session_id, event="input.queued",
                                        data={"message_id": message.id, "queue_position": item.id})
            return SubmitResult("accepted", Disposition.QUEUED, message.id, turn_id)

        # 抢锁反复失败：保守地排队，不丢输入。
        item = await self._queue.enqueue(
            owner_id=owner_id, session_id=session_id, message_id=message.id,
            client_message_id=client_message_id, text=text)
        await self._control.publish(session_id=session_id, event="input.queued",
                                    data={"message_id": message.id, "queue_position": item.id})
        return SubmitResult("accepted", Disposition.QUEUED, message.id, None)

    async def rerun(self, *, owner_id: int, session_id: int, character_id: str, text: str,
                    message_ids: list[int], alt_of: int | None = None) -> str | None:
        """重新生成 / 继续 / 重试：会话空闲才开始；忙则返回 None（路由层映射为 409）。

        ``alt_of``：被重新生成的那条助手回复。新回复会作为它的另一个候选保存（左右滑动切换）。"""
        return await self._start(owner_id=owner_id, session_id=session_id, character_id=character_id,
                                 text=text, message_ids=message_ids, alt_of=alt_of)

    async def _start(self, *, owner_id: int, session_id: int, character_id: str, text: str,
                     message_ids: list[int], alt_of: int | None = None) -> str | None:
        turn_id = new_ulid()
        owner = f"{self._process}:{turn_id}"
        if not await self._control.acquire_lock(session_id=session_id, owner=owner):
            return None
        # 围栏：拿到锁就取一个更大的号并记到会话上。之后这把锁哪怕过期被别人接手，
        # 旧回合写回复时围栏号已不是最新，写入会被拒绝（chat-agent-context-design.md §4.2）。
        fencing: dict[str, int] = {}
        fence: int | None = None
        if self._sessions is not None:
            fence = await self._control.next_fence(session_id=session_id)
            fencing["fence"] = fence
        if alt_of is not None:
            fencing["alt_of"] = alt_of   # 只在有值时传：不关心候选的启动回调不用改
        # 这一步走库，init_turn 走 Redis，两者互不依赖——并发，省一次往返。
        # 它们是接在前两行之后剩下的最后两次串行等待，各 180 ms 量级。
        if fence is not None:
            _, _ = await asyncio.gather(
                self._sessions.advance_fence(session_id=session_id, fence=fence),
                self._control.init_turn(session_id=session_id, turn_id=turn_id, message_ids=message_ids))
        else:
            await self._control.init_turn(session_id=session_id, turn_id=turn_id, message_ids=message_ids)
        await self._start_turn(owner_id=owner_id, session_id=session_id, character_id=character_id,
                               turn_id=turn_id, owner=owner, text=text, message_ids=message_ids, **fencing)
        return turn_id
