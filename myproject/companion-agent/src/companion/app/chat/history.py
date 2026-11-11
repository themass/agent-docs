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
import uuid
from datetime import UTC, datetime
from typing import Any

from companion.domain.history.summary import RESUMMARIZE_JOB
from companion.ports.conversation import ConversationStatePort, lc_assistant_id, lc_user_id
from companion.ports.jobs import JobStore
from companion.ports.store import MessageRecord, MessageStore
from companion.ports.turn_control import TurnControlPort

log = logging.getLogger("companion.history")

INTERRUPTED_SUFFIX = "（回复被中断）"


class HistoryBusy(RuntimeError):
    """会话正在进行回合；历史操作要等它结束。"""


def lc_ids_of(message: MessageRecord) -> list[str]:
    if message.role == "user" or message.kind == "proactive":
        return [lc_user_id(message.id)]
    ids = [str(i) for i in (message.meta or {}).get("lc_ids", []) if i]
    ids.append(lc_assistant_id(message.id))   # 中断回复的补记
    return ids


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

    async def _resummarize_later(self, *, owner_id: int, session_id: int, reason: str) -> None:
        if self._jobs is None:
            return
        await self._jobs.enqueue(kind=RESUMMARIZE_JOB, payload={"owner_id": owner_id, "session_id": session_id},
                                 run_after=_now(), dedupe_key=f"{RESUMMARIZE_JOB}:{session_id}:{reason}")

    async def delete(self, *, owner_id: int, message_id: int) -> bool:
        message = await self._messages.get(owner_id=owner_id, message_id=message_id)
        if message is None:
            return False
        if self._conversation is None:
            return await self._messages.soft_delete(owner_id=owner_id, message_id=message_id)
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

    async def note_interrupted(self, *, session_id: int, assistant_message_id: int, text: str) -> None:
        """回合被中断但已有部分回复：补记到线程，让模型知道上一句说到哪里。
        由回合收尾调用，此时回合仍持有会话锁，这里不再加锁。"""
        if self._conversation is None or not text.strip():
            return
        await self._conversation.append_assistant(
            session_id=session_id, lc_id=lc_assistant_id(assistant_message_id), text=text + INTERRUPTED_SUFFIX)
