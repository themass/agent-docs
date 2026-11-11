"""定时提醒的 SQL 存储（Postgres 用 SKIP LOCKED 认领；MySQL 退回条件更新）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.sql.schema import reminder
from companion.ports.reminders import CANCELLED, CLAIMED, FAILED, PENDING, SENT, ReminderRecord


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _record(row: Any) -> ReminderRecord:
    return ReminderRecord(
        id=row["id"], owner_id=row["owner_id"], session_id=row["session_id"], role_id=row["role_id"],
        due_at=row["due_at"], timezone=row["timezone"], content=row["content"], status=row["status"],
        attempts=row["attempts"], created_at=row["created_at"], confirmation_id=row["confirmation_id"],
        sent_turn_id=row["sent_turn_id"])


class SqlReminderStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create(self, *, owner_id: int, session_id: int, role_id: str, due_at: datetime, timezone: str,
                     content: str, confirmation_id: str | None) -> ReminderRecord:
        now = _now()
        try:
            async with self._engine.begin() as conn:
                res = await conn.execute(insert(reminder).values(
                    owner_id=owner_id, session_id=session_id, role_id=role_id, due_at=due_at, timezone=timezone,
                    content=content, status=PENDING, attempts=0, confirmation_id=confirmation_id,
                    created_at=now, updated_at=now))
                new_id = res.inserted_primary_key[0]
        except IntegrityError:
            if confirmation_id is None:
                raise
            async with self._engine.connect() as conn:
                row = (await conn.execute(select(reminder).where(
                    reminder.c.confirmation_id == confirmation_id))).mappings().one()
            return _record(row)
        return ReminderRecord(new_id, owner_id, session_id, role_id, due_at, timezone, content, PENDING, 0, now,
                              confirmation_id, None)

    async def list_for_owner(self, *, owner_id: int, include_done: bool = False,
                             limit: int = 50) -> list[ReminderRecord]:
        cond = [reminder.c.owner_id == owner_id]
        if not include_done:
            cond.append(reminder.c.status.in_([PENDING, CLAIMED]))
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(reminder).where(and_(*cond))
                    .order_by(reminder.c.due_at).limit(limit))).mappings().all()
        return [_record(r) for r in rows]

    async def cancel(self, *, owner_id: int, reminder_id: int) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(reminder).where(and_(
                reminder.c.id == reminder_id, reminder.c.owner_id == owner_id, reminder.c.status == PENDING))
                .values(status=CANCELLED, updated_at=_now()))
        return res.rowcount == 1

    def _due(self, now: datetime):
        return or_(
            and_(reminder.c.status == PENDING, reminder.c.due_at <= now),
            and_(reminder.c.status == CLAIMED, reminder.c.lease_until <= now),
        )

    async def claim_due(self, *, owner: str, now: datetime, lease_until: datetime,
                        limit: int) -> list[ReminderRecord]:
        if self._engine.dialect.name == "postgresql":
            async with self._engine.begin() as conn:
                ids = (await conn.execute(select(reminder.c.id).where(self._due(now)).order_by(reminder.c.due_at)
                       .limit(limit).with_for_update(skip_locked=True))).scalars().all()
                if not ids:
                    return []
                rows = (await conn.execute(update(reminder).where(reminder.c.id.in_(ids))
                        .values(status=CLAIMED, lease_owner=owner, lease_until=lease_until,
                                attempts=reminder.c.attempts + 1, updated_at=now)
                        .returning(reminder))).mappings().all()
            return sorted((_record(r) for r in rows), key=lambda r: r.due_at)

        # 没有 SKIP LOCKED 的方言：先取候选，再逐条条件更新，rowcount == 1 才算拿到。
        async with self._engine.connect() as conn:
            ids = (await conn.execute(select(reminder.c.id).where(self._due(now))
                   .order_by(reminder.c.due_at).limit(limit))).scalars().all()
        claimed: list[ReminderRecord] = []
        for rid in ids:
            async with self._engine.begin() as conn:
                res = await conn.execute(update(reminder).where(and_(reminder.c.id == rid, self._due(now)))
                                         .values(status=CLAIMED, lease_owner=owner, lease_until=lease_until,
                                                 attempts=reminder.c.attempts + 1, updated_at=now))
                if res.rowcount != 1:
                    continue
                row = (await conn.execute(select(reminder).where(reminder.c.id == rid))).mappings().one()
            claimed.append(_record(row))
        return claimed

    async def mark_sent(self, *, reminder_id: int, owner: str, turn_id: str | None) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(reminder).where(and_(
                reminder.c.id == reminder_id, reminder.c.lease_owner == owner, reminder.c.status == CLAIMED))
                .values(status=SENT, sent_turn_id=turn_id, updated_at=_now()))
        return res.rowcount == 1

    async def release(self, *, reminder_id: int, owner: str, error: str, retry_at: datetime | None,
                      max_attempts: int) -> bool:
        async with self._engine.begin() as conn:
            row = (await conn.execute(select(reminder.c.attempts).where(and_(
                reminder.c.id == reminder_id, reminder.c.lease_owner == owner,
                reminder.c.status == CLAIMED)))).first()
            if row is None:
                return False
            done = retry_at is None or row[0] >= max_attempts
            values: dict[str, Any] = {"status": FAILED if done else PENDING, "last_error": error[:500],
                                      "lease_owner": None, "lease_until": None, "updated_at": _now()}
            if not done:
                values["due_at"] = retry_at
            res = await conn.execute(update(reminder).where(reminder.c.id == reminder_id).values(**values))
        return res.rowcount == 1
