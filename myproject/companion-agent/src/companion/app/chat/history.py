"""编辑、删除、重新生成：消息表与对话线程一起改（chat-agent-next-plan.md §2.2、§7 决策 3）。

规则：
- 消息表是原始内容的权威；对话线程是模型的工作上下文。两边必须一致，否则用户删掉的话模型仍会看到。
- 线程里还在的消息：按 id 直接移除 / 替换；
- 已经被摘要压缩掉的消息：线程里找不到，就入队重建摘要（从消息表里未删除的内容重新生成），
  保证删掉的内容最终也从摘要里消失；
- 所有线程写入都要持有会话锁：回合进行中返回忙（路由层映射为 409），不和回合抢写。
"""

from __future__ import annotations

import logging
import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from companion.domain.history.summary import RESUMMARIZE_JOB

# 清空历史时等回合结束：约 2 秒内每 200ms 试一次，抢不到再报 409。
CLEAR_LOCK_ATTEMPTS = 10
CLEAR_LOCK_DELAY = 0.2
from companion.ports.conversation import ConversationStatePort, lc_assistant_id, lc_user_id
from companion.ports.jobs import JobStore
from companion.ports.store import MessageRecord, MessageStore
from companion.ports.turn_control import TurnControlPort

log = logging.getLogger("companion.history")

INTERRUPTED_SUFFIX = "（回复被中断）"


class HistoryBusy(RuntimeError):
    """会话正在进行回合；历史操作要等它结束。"""


class NotLatest(RuntimeError):
    """候选回复只能在「最新一轮」切换：线程是顺序的，往中间插入会让模型看到错乱的对话。"""


def lc_ids_of(message: MessageRecord) -> list[str]:
    if message.role == "user" or message.kind == "proactive":
        return [lc_user_id(message.id)]
    ids = [str(i) for i in (message.meta or {}).get("lc_ids", []) if i]
    ids.append(lc_assistant_id(message.id))   # 中断回复的补记
    return ids


async def find_reply(messages: MessageStore, *, owner_id: int, session_id: int, user_message_id: int) -> int | None:
    """这条用户消息当前的回复（最新一轮才有意义）：它之后、下一条用户消息之前被选中的最后一条助手回复。
    后面已经有别的用户消息（不是最新一轮）返回 None：旧的轮次不做候选，重新生成按普通消息写入。"""
    later = await messages.list_after(owner_id=owner_id, session_id=session_id, after_id=user_message_id, limit=50)
    reply: int | None = None
    for m in later:
        if m.role == "assistant":
            reply = m.id
        elif m.role == "user" or m.kind == "proactive":
            return None
    return reply


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class HistoryService:
    def __init__(self, *, messages: MessageStore, control: TurnControlPort,
                 conversation: ConversationStatePort | None = None, jobs: JobStore | None = None,
                 timeline: Any = None) -> None:
        """``timeline``：时间线存储。删除或编辑用户消息时，由这条消息得来（非手动添加）的事件置 stale；
        物理删除会话时清掉。在会话锁内执行，与回合互斥。"""
        self._messages = messages
        self._control = control
        self._conversation = conversation
        self._jobs = jobs
        self._timeline = timeline

    async def _stale_events(self, *, owner_id: int, message_id: int) -> None:
        if self._timeline is None:
            return
        try:
            await self._timeline.mark_stale_for_source(owner_id=str(owner_id), message_id=str(message_id))
        except Exception:  # noqa: BLE001 —— 联动失败不该让删除 / 编辑失败
            pass

    async def _locked(self, session_id: int):
        owner = f"history:{uuid.uuid4().hex}"
        if not await self._control.acquire_lock(session_id=session_id, owner=owner):
            raise HistoryBusy(session_id)
        return owner

    async def _acquire_with_retry(self, session_id: int, *, attempts: int = CLEAR_LOCK_ATTEMPTS,
                                 delay: float = CLEAR_LOCK_DELAY) -> str:
        """抢会话锁；正在生成的回合结束后再清。抢不到才抛 HistoryBusy。"""
        for i in range(attempts):
            owner = f"history:{uuid.uuid4().hex}"
            if await self._control.acquire_lock(session_id=session_id, owner=owner):
                return owner
            if i < attempts - 1:
                await asyncio.sleep(delay)
        raise HistoryBusy(session_id)

    async def _resummarize_later(self, *, owner_id: int, session_id: int, reason: str) -> None:
        if self._jobs is None:
            return
        await self._jobs.enqueue(kind=RESUMMARIZE_JOB, payload={"owner_id": owner_id, "session_id": session_id},
                                 run_after=_now(), dedupe_key=f"{RESUMMARIZE_JOB}:{session_id}:{reason}")

    # ---- 候选回复（左右滑动切换）----

    async def _is_latest(self, message: MessageRecord, siblings: list[MessageRecord]) -> bool:
        """这一组候选之后，会话里没有别的（选中且未删除的）消息。"""
        last = max([m.id for m in siblings] + [message.id])
        return not await self._messages.list_after(owner_id=message.owner_id, session_id=message.session_id,
                                                   after_id=last, limit=1)

    async def _put_in_thread(self, *, session_id: int, message: MessageRecord) -> None:
        """把一条候选的最终文本作为助手消息放进线程末尾（工具调用的中间步骤不再还原）。"""
        text = message.content + (INTERRUPTED_SUFFIX if message.interrupted else "")
        if text.strip():
            await self._conversation.append_assistant(
                session_id=session_id, lc_id=lc_assistant_id(message.id), text=text)

    async def reply_to(self, *, owner_id: int, session_id: int, user_message_id: int) -> int | None:
        return await find_reply(self._messages, owner_id=owner_id, session_id=session_id,
                                user_message_id=user_message_id)

    async def select_alternative(self, *, owner_id: int, message_id: int) -> MessageRecord | None:
        """切换到这条候选。返回切换后的消息；不存在或不是候选返回 None；不在最新一轮抛 NotLatest。"""
        target = await self._messages.get(owner_id=owner_id, message_id=message_id)
        if target is None or target.role != "assistant" or target.alt_group is None:
            return None
        group = target.alt_group
        sid = target.session_id
        if self._conversation is None:
            ok = await self._messages.select_alternative(owner_id=owner_id, session_id=sid, alt_group=group,
                                                         message_id=message_id)
            return await self._messages.get(owner_id=owner_id, message_id=message_id) if ok else None
        owner = await self._locked(sid)
        try:
            siblings = await self._messages.alternatives(owner_id=owner_id, session_id=sid, alt_group=group)
            if message_id not in {m.id for m in siblings}:
                return None
            current = next((m for m in siblings if m.alt_selected), None)
            if current is not None and current.id == message_id:
                return target
            if not await self._is_latest(target, siblings):
                raise NotLatest(message_id)
            if not await self._messages.select_alternative(owner_id=owner_id, session_id=sid, alt_group=group,
                                                           message_id=message_id):
                return None
            removed = await self._conversation.remove(session_id=sid, ids=lc_ids_of(current)) if current else 0
            if current is not None and removed == 0:
                # 旧的那条已被摘要压缩进去：摘要里还留着它的内容，重建一次
                await self._resummarize_later(owner_id=owner_id, session_id=sid,
                                              reason=f"select:{message_id}:{uuid.uuid4().hex[:8]}")
            await self._put_in_thread(session_id=sid, message=target)
        finally:
            await self._control.release_lock(session_id=sid, owner=owner)
        return await self._messages.get(owner_id=owner_id, message_id=message_id)

    async def _after_alt_deleted(self, *, message: MessageRecord) -> None:
        """删掉的是一组候选里的一条。被删的若是当前选中的：最新一轮 → 选最新的剩余候选顶上；
        不是最新一轮 → 整组删除（往中间放回候选会让线程错乱）。没被选中的候选直接删，不动线程。"""
        if message.alt_group is None or not message.alt_selected:
            return
        sid, oid = message.session_id, message.owner_id
        siblings = await self._messages.alternatives(owner_id=oid, session_id=sid, alt_group=message.alt_group)
        if not siblings:
            return
        if await self._is_latest(message, siblings):
            promoted = siblings[-1]
            await self._messages.select_alternative(owner_id=oid, session_id=sid, alt_group=message.alt_group,
                                                    message_id=promoted.id)
            if self._conversation is not None:
                await self._put_in_thread(session_id=sid, message=promoted)
            return
        for m in siblings:
            await self._messages.soft_delete(owner_id=oid, message_id=m.id)

    async def delete(self, *, owner_id: int, message_id: int) -> bool:
        message = await self._messages.get(owner_id=owner_id, message_id=message_id)
        if message is None:
            return False
        if self._conversation is None:
            if not await self._messages.soft_delete(owner_id=owner_id, message_id=message_id):
                return False
            await self._after_alt_deleted(message=message)
            return True
        owner = await self._locked(message.session_id)
        try:
            if not await self._messages.soft_delete(owner_id=owner_id, message_id=message_id):
                return False
            if message.role == "user":
                await self._stale_events(owner_id=owner_id, message_id=message_id)
            wanted = lc_ids_of(message)
            removed = await self._conversation.remove(session_id=message.session_id, ids=wanted)
            if removed == 0:
                # 线程里一条都没有：要么已被摘要压缩，要么从未进入线程（例如排队中被撤回）。
                # 前者必须重建摘要；后者重建一次也无害。
                await self._resummarize_later(owner_id=owner_id, session_id=message.session_id,
                                              reason=f"delete:{message_id}")
            await self._after_alt_deleted(message=message)
        finally:
            await self._control.release_lock(session_id=message.session_id, owner=owner)
        return True

    async def edit(self, *, owner_id: int, message_id: int, content: str) -> MessageRecord | None:
        message = await self._messages.get(owner_id=owner_id, message_id=message_id)
        if message is None or message.role != "user":
            return None
        if self._conversation is None:
            ok = await self._messages.edit(owner_id=owner_id, message_id=message_id, content=content)
            return await self._messages.get(owner_id=owner_id, message_id=message_id) if ok else None
        owner = await self._locked(message.session_id)
        try:
            if not await self._messages.edit(owner_id=owner_id, message_id=message_id, content=content):
                return None
            # 编辑后旧事件作废（内容可能变了），时间线重建由下一次抽取或用户手动修正
            await self._stale_events(owner_id=owner_id, message_id=message_id)
            replaced = await self._conversation.replace_user_text(
                session_id=message.session_id, lc_id=lc_user_id(message_id), text=content)
            if not replaced:
                await self._resummarize_later(owner_id=owner_id, session_id=message.session_id,
                                              reason=f"edit:{message_id}:{uuid.uuid4().hex[:8]}")
        finally:
            await self._control.release_lock(session_id=message.session_id, owner=owner)
        return await self._messages.get(owner_id=owner_id, message_id=message_id)

    async def forget_replies_after(self, *, owner_id: int, session_id: int, user_message_id: int) -> int:
        """重新生成之前：把这条用户消息之后的助手回复从线程里移除，模型不会看到旧答案。
        消息表里的旧回复保留（界面可以作为备选回复展示）。"""
        if self._conversation is None:
            return 0
        owner = await self._locked(session_id)
        try:
            later = await self._messages.list_after(owner_id=owner_id, session_id=session_id,
                                                    after_id=user_message_id, limit=200)
            ids = [i for m in later if m.role == "assistant" for i in lc_ids_of(m)]
            return await self._conversation.remove(session_id=session_id, ids=ids) if ids else 0
        finally:
            await self._control.release_lock(session_id=session_id, owner=owner)

    async def clear(self, *, owner_id: int, session_id: int) -> int:
        """清空一个会话的历史：消息表软删 + 大脑线程里的对话一起清掉。

        两处都要清，否则界面空了、模型还记得——下一次回复会引用「你们之前说过」的内容，
        用户会认为是 bug。中途拿到会话锁才清：正在生成的回合不能被抽掉底部。
        """
        # 用户刚发完消息就点「清空」是很常见的操作，而回合结束前锁还在。
        # 直接失败会让用户看到「操作失败」，所以先等一会儿再放弃。
        owner = await self._acquire_with_retry(session_id)
        try:
            if self._conversation is not None:
                await self._conversation.reset(session_id=session_id)
                await self._resummarize_later(owner_id=owner_id, session_id=session_id, reason="cleared")
            return await self._messages.clear(owner_id=owner_id, session_id=session_id)
        finally:
            await self._control.release_lock(session_id=session_id, owner=owner)

    async def note_interrupted(self, *, session_id: int, assistant_message_id: int, text: str) -> None:
        """回合被中断但已有部分回复：补记到线程，让模型知道上一句说到哪里。
        由回合收尾调用，此时回合仍持有会话锁，这里不再加锁。"""
        if self._conversation is None or not text.strip():
            return
        await self._conversation.append_assistant(
            session_id=session_id, lc_id=lc_assistant_id(assistant_message_id), text=text + INTERRUPTED_SUFFIX)
