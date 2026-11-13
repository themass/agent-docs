"""定时提醒：创建（工具确认后）、查看、取消，以及到点发起主动回合（chat-agent-next-plan.md 阶段 4）。

多副本：调度器在每个 worker 上都跑；认领在存储里互斥（Postgres SKIP LOCKED），租约过期可被他人接手。
到点后不直接发消息，而是提交一个主动回合：角色、记忆、安全检查、上下文都与普通回合一致；
会话正忙时它会排队。推送只是提醒用户回来看，消息本体从会话历史与 SSE 读取。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from companion.proactive.reminders_domain import (
    MAX_ATTEMPTS,
    RETRY_DELAY,
    normalize_content,
    normalize_due,
    proactive_instruction,
)
from companion.proactive.push_port import PushMessage, PushPort
from companion.proactive.reminders_port import ReminderRecord, ReminderStore
from companion.store.port import SessionStore

log = logging.getLogger("companion.reminders")

LEASE = timedelta(minutes=2)
BATCH = 20

# 提交主动回合：(owner_id, session_id, role_id, text) -> turn_id 或 None（排队时）。
# 会话已不存在（用户删了）时抛 SessionGone：提醒直接结束，不重试、不推送。
SubmitProactive = Callable[[int, int, str, str], Awaitable[str | None]]


class SessionGone(LookupError):
    pass


def _naive(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(tzinfo=None)


class ReminderService:
    def __init__(self, *, store: ReminderStore, sessions: SessionStore,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._store = store
        self._sessions = sessions
        self._clock = clock

    async def create(self, *, owner_id: int, session_id: int, at: datetime, timezone: str | None, content: str,
                     confirmation_id: str | None) -> ReminderRecord:
        """工具确认后调用。时间、内容不合法时抛 ReminderInvalid（工具把它转成给模型的错误说明）。"""
        due = normalize_due(at, timezone=timezone, now=self._clock())
        text = normalize_content(content)
        session = await self._sessions.get(owner_id=owner_id, session_id=session_id)
        if session is None:
            raise LookupError(f"session {session_id} not found")
        return await self._store.create(owner_id=owner_id, session_id=session_id, role_id=session.role_id,
                                        due_at=due.utc, timezone=due.timezone, content=text,
                                        confirmation_id=confirmation_id)

    async def list(self, *, owner_id: int, include_done: bool = False) -> list[ReminderRecord]:
        return await self._store.list_for_owner(owner_id=owner_id, include_done=include_done)

    async def cancel(self, *, owner_id: int, reminder_id: int) -> bool:
        return await self._store.cancel(owner_id=owner_id, reminder_id=reminder_id)


class ReminderDispatcher:
    def __init__(self, *, store: ReminderStore, submit: SubmitProactive, owner: str,
                 push: PushPort | None = None) -> None:
        self._store = store
        self._submit = submit
        self._owner = owner
        self._push = push

    async def run_once(self, now: datetime) -> int:
        """认领到期的提醒并逐条发起主动回合。返回本次处理的条数。"""
        current = _naive(now)
        claimed = await self._store.claim_due(owner=self._owner, now=current, lease_until=current + LEASE,
                                              limit=BATCH)
        for item in claimed:
            await self._dispatch(item, current)
        return len(claimed)

    async def _dispatch(self, item: ReminderRecord, now: datetime) -> None:
        text = proactive_instruction(content=item.content, due_utc=item.due_at, timezone=item.timezone)
        try:
            turn_id = await self._submit(item.owner_id, item.session_id, item.role_id, text)
        except SessionGone:
            await self._store.release(reminder_id=item.id, owner=self._owner, error="session_gone",
                                      retry_at=None, max_attempts=MAX_ATTEMPTS)
            return
        except Exception as exc:  # noqa: BLE001 —— 失败稍后重试，超过次数置 failed
            log.warning("reminder dispatch failed", extra={"reminder_id": item.id, "error": type(exc).__name__})
            await self._store.release(reminder_id=item.id, owner=self._owner, error=type(exc).__name__,
                                      retry_at=now + RETRY_DELAY, max_attempts=MAX_ATTEMPTS)
            return
        await self._store.mark_sent(reminder_id=item.id, owner=self._owner, turn_id=turn_id)
        if self._push is not None:
            await self._push.send(PushMessage(
                owner_id=item.owner_id, title="你有一条新消息", body=item.content[:60],
                data={"session_id": str(item.session_id), "reminder_id": str(item.id), "turn_id": turn_id or ""}))
