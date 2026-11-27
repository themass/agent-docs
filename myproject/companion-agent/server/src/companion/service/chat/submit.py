"""提交与重跑（D §6.1、§6.6、A §5.1）。

提交顺序固定：幂等 → 安全检测 → 落库 → Redis 原子判定 → 按处置执行。
安全检测对每条输入都执行，包括之后会被合并、插话或排队的输入（T §1、M11）。
重跑（重新生成、继续、重试）不经过判定：它只能在会话空闲时开始，否则返回忙。
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from companion.agent.util.ids import new_ulid
from companion.agent.middleware.safety import check_input
from companion.service.turn.queue import Disposition
from companion.db.port import MessageStore, QueueStore, SessionStore
from companion.service.turn.control import TurnControlPort

log = logging.getLogger("companion.chat.submit")

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
                     kind: str = "chat", attachments: list[dict[str, Any]] | None = None,
                     location: dict[str, Any] | None = None) -> SubmitResult:
        """``role`` / ``kind``：用户消息是 user/chat；服务端发起的主动回合（到点提醒）是 system/proactive，
        走同一条判定路径（会话忙时排队），模型看到的是一条带标记的指令。

        ``location``（P2-13）：位置消息的结构化坐标，路由层已把 kind 定为 location、
        并把模型可读的文本放进 ``text``；这里只负责把它原样存进 ``meta.location``，
        历史接口按类型带回给客户端渲染坐标气泡。"""
        if client_message_id:
            existing = await self._messages.find_by_client_id(
                owner_id=owner_id, session_id=session_id, client_message_id=client_message_id)
            if existing is not None:
                return await self._redrive_duplicate(owner_id=owner_id, session_id=session_id,
                                                     character_id=character_id, existing=existing)

        denied = check_input(text)
        if denied is not None:
            return SubmitResult("denied", None, 0, None, reason=denied)

        # 附件（图片/文件）跟着这条用户消息一起存进 meta：一个上传只属于一条消息，
        # 单独建表反而要额外维护「哪条消息引用哪个上传」的关系。location 同等待遇。
        meta: dict[str, Any] = {}
        if attachments:
            meta["attachments"] = list(attachments)
        if location:
            meta["location"] = dict(location)
        message = await self._messages.append(
            owner_id=owner_id, session_id=session_id, role=role, content=text, kind=kind,
            client_message_id=client_message_id, turn_id=None, meta=meta)
        # message.created 不立刻发，而是攒着，和分支决定后的那条事件合成一次 Redis 往返。
        # 原先它是独立一次 publish，STARTED 之后回合进程再发一次 turn.started——两次
        # 往返各 190 ms 量级，而这两条事件客户端都不依赖彼此之间的时间差
        # （message.created 幂等，turn.started 对还没到的消息 id 是 no-op）。
        created: tuple[str, dict[str, Any]] = (
            "message.created",
            {"message_id": message.id, "client_message_id": client_message_id, "role": role,
             "kind": kind, "content": text, "created_at": message.created_at.isoformat()})

        for _ in range(LOCK_RETRIES):
            disposition, turn_id = await self._control.decide(
                session_id=session_id, message_id=str(message.id), text=text, steerable=steerable,
                steer_budget=self._steer_budget, max_restarts=self._max_restarts)

            if disposition is Disposition.STARTED:
                started = await self._start(owner_id=owner_id, session_id=session_id,
                                            character_id=character_id, text=text, message_ids=[message.id],
                                            also_publish=(created,))
                if started is not None:
                    return SubmitResult("accepted", Disposition.STARTED, message.id, started)
                continue  # 别的请求刚抢到锁：回到判定，这次大概率是合并/插话/排队

            if disposition in (Disposition.MERGED, Disposition.STEERED):
                # 控制消息已由 Lua 原子写入 turn:{tid}:ctl；回合进程会接手并挂接消息。
                event = "input.merged" if disposition is Disposition.MERGED else "input.steered"
                await self._control.publish_many(session_id=session_id, events=[
                    created, (event, {"message_id": message.id, "turn_id": turn_id})])
                return SubmitResult("accepted", disposition, message.id, turn_id)

            item = await self._queue.enqueue(
                owner_id=owner_id, session_id=session_id, message_id=message.id,
                client_message_id=client_message_id, text=text)
            await self._control.publish_many(session_id=session_id, events=[
                created, ("input.queued", {"message_id": message.id, "queue_position": item.id})])
            return SubmitResult("accepted", Disposition.QUEUED, message.id, turn_id)

        # 抢锁反复失败：保守地排队，不丢输入。
        item = await self._queue.enqueue(
            owner_id=owner_id, session_id=session_id, message_id=message.id,
            client_message_id=client_message_id, text=text)
        await self._control.publish_many(session_id=session_id, events=[
            created, ("input.queued", {"message_id": message.id, "queue_position": item.id})])
        return SubmitResult("accepted", Disposition.QUEUED, message.id, None)

    async def rerun(self, *, owner_id: int, session_id: int, character_id: str, text: str,
                    message_ids: list[int], alt_of: int | None = None) -> str | None:
        """重新生成 / 继续 / 重试：会话空闲才开始；忙则返回 None（路由层映射为 409）。

        ``alt_of``：被重新生成的那条助手回复。新回复会作为它的另一个候选保存（左右滑动切换）。"""
        return await self._start(owner_id=owner_id, session_id=session_id, character_id=character_id,
                                 text=text, message_ids=message_ids, alt_of=alt_of)

    async def _redrive_duplicate(self, *, owner_id: int, session_id: int, character_id: str,
                                 existing: Any) -> SubmitResult:
        """重发命中幂等时的处理。

        原来的判据只有一句「这条 client_message_id 存过」→ `duplicate`，HTTP 仍是 202。
        2026-11-28 线上 session 39 就是这么把用户吞掉的：原回合在 16:47:51 的重启里死了，
        17:04:45 的重发被判成 duplicate，既不起新回合、也不报错——用户那边是「发了没反应」，
        而客户端在 17:09–17:11 打了约 40 次 /cancel。

        所以现在多问一句：**那条回合还活着吗，它回答过吗。**
        - 还活着（会话的活锁就是这个 turn_id）→ 真是重复，按原样回 duplicate，别抢它的工作。
        - 已经死了但回答过了 → 也回 duplicate（重驱动会让用户看到两遍同样的话）。
        - 还在排队（turn_id 为空但有队列条目）→ 回 duplicate，排空会带它，不能另起一个回合。
        - 已经死了且没回答 → 这是唯一会静默丢消息的情形，重驱动它，回 `accepted`；
          会话忙就把它转成排队（回 `accepted` + QUEUED），因为排队正是「稍后一定会回答」的
          既有语义——不这样做的话，这条消息在回合状态被清掉后就再也没人捞得起来了。

        回 `accepted` 而不是发明新状态：Android 现有实现对 accepted 的处理就是「等这条
        回合的流」，对 QUEUED 的处理就是等排空，所以修复不需要端上配合（本次任务不动 Android 仓库）。
        """
        dead_turn_id = existing.turn_id
        if dead_turn_id is not None:
            live = await self._control.active_turn(session_id=session_id)
            if live and live.get("turn_id") == dead_turn_id:
                return SubmitResult("duplicate", None, existing.id, dead_turn_id)
        else:
            # turn_id 为空不等于没在处理：排队中的消息就是这个状态（submit 先落库、
            # 后判定，排队的条目要等排空才挂上 turn_id）。这时重驱动会让同一个人被回答两遍。
            for status in ("queued", "draining"):
                items = await self._queue.list_status(owner_id=owner_id, session_id=session_id,
                                                      status=status)
                if any(i.message_id == existing.id for i in items):
                    return SubmitResult("duplicate", None, existing.id, None)

        # 回合已经不在。它有没有已经把答案写出来？
        if dead_turn_id is not None:
            rows = await self._messages.list_by_turn(owner_id=owner_id, session_id=session_id,
                                                     turn_id=dead_turn_id)
            if any(m.role == "assistant" for m in rows):
                return SubmitResult("duplicate", None, existing.id, dead_turn_id)

        turn_id = await self.rerun(owner_id=owner_id, session_id=session_id, character_id=character_id,
                                   text=existing.content, message_ids=[existing.id])
        if turn_id is None:
            # 会话正被别的回合占着：不能并发驱动，转成排队——占场那个收尾后排空会带上它。
            item = await self._queue.enqueue(owner_id=owner_id, session_id=session_id,
                                             message_id=existing.id,
                                             client_message_id=existing.client_message_id,
                                             text=existing.content)
            await self._control.publish(session_id=session_id, event="input.queued",
                                        data={"message_id": existing.id, "queue_position": item.id})
            log.warning("resend of message=%s hit a dead turn=%s but session=%s is busy -> queued",
                        existing.id, dead_turn_id, session_id)
            return SubmitResult("accepted", Disposition.QUEUED, existing.id, None)
        log.warning("resend redrove message=%s dead_turn=%s -> turn=%s session=%s",
                    existing.id, dead_turn_id, turn_id, session_id)
        return SubmitResult("accepted", Disposition.STARTED, existing.id, turn_id)

    async def _start(self, *, owner_id: int, session_id: int, character_id: str, text: str,
                     message_ids: list[int], alt_of: int | None = None,
                     also_publish: tuple[tuple[str, dict[str, Any]], ...] = ()) -> str | None:
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
        # turn.started 在这里发，不留给后台回合进程：它和 also_publish 里攒下的
        # message.created 合成一次往返，而且顺序上是"客户端先看到回合开始，再看到内容"。
        # 客户端对这两条的先后不敏感（message.created 幂等、turn.started 对未到的消息是 no-op），
        # 但客户端**依赖** turn.started 早于同一回合的第一个 step——step 会重置 active.steps。
        # 在启动回合之前发，这个顺序由构造保证，不靠调度运气。
        await self._control.publish_many(session_id=session_id, events=[
            *also_publish,
            ("turn.started", {"turn_id": turn_id, "user_message_ids": message_ids})])
        await self._start_turn(owner_id=owner_id, session_id=session_id, character_id=character_id,
                               turn_id=turn_id, owner=owner, text=text, message_ids=message_ids, **fencing)
        return turn_id
