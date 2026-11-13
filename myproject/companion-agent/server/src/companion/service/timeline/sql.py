"""时间线的 Postgres 实现（MySQL 兼容）。语义见 ports/timeline.py 与 domain/timeline/models.py。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import timeline_event
from companion.service.timeline.models import (
    EventKind,
    EventOrigin,
    EventStatus,
    Recurrence,
    TimelineEvent,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


def _naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _row(event: TimelineEvent, now: datetime) -> dict[str, Any]:
    nxt = event.next_at(now=now)
    return {
        "public_id": event.id, "owner_id": int(event.user_id), "role_id": event.source_character_id or "",
        "session_id": event.session_id, "source_message_id": event.source_message_id or None,
        "origin": event.origin.value, "kind": event.kind.value, "title": event.title,
        "at_utc": _naive(event.at), "timezone": "UTC", "all_day": event.all_day,
        "recurrence": event.recurrence.value, "next_at_utc": _naive(nxt) if nxt else None,
        "status": event.status.value, "confidence": float(event.confidence),
        "reminder_id": event.reminder_id, "dedupe_key": event.dedupe_key,
    }


def _event(row) -> TimelineEvent:
    return TimelineEvent(
        id=row["public_id"], user_id=str(row["owner_id"]), kind=EventKind(row["kind"]), title=row["title"],
        at=_aware(row["at_utc"]), source_character_id=row["role_id"] or "",
        source_message_id=row["source_message_id"] or "", session_id=row["session_id"],
        reminder_id=row["reminder_id"], origin=EventOrigin(row["origin"]), confidence=row["confidence"],
        status=EventStatus(row["status"]), recurrence=Recurrence(row["recurrence"]),
        all_day=bool(row["all_day"]),
        created_at=_aware(row["created_at"]) if row["created_at"] else _aware(row["at_utc"]))


class SqlTimelineStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    # ---- 写 ----

    async def upsert(self, event: TimelineEvent) -> TimelineEvent:
        now = _now()
        values = _row(event, now)
        async with self._engine.begin() as conn:
            existing = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.owner_id == values["owner_id"], timeline_event.c.role_id == values["role_id"],
                timeline_event.c.dedupe_key == values["dedupe_key"],
            )))).mappings().first()
            if existing is not None:
                merged = _event(existing)
                merged.at = event.at
                merged.confidence = max(merged.confidence, event.confidence)
                merged.reminder_id = event.reminder_id or merged.reminder_id
                merged.source_message_id = event.source_message_id or merged.source_message_id
                # 重新提到一件已被编辑作废的事：恢复成 scheduled
                if event.status == EventStatus.SCHEDULED and merged.status == EventStatus.STALE:
                    merged.status = EventStatus.SCHEDULED
                await conn.execute(update(timeline_event).where(timeline_event.c.id == existing["id"])
                                   .values(**_row(merged, now), updated_at=now))
                return merged
            try:
                await conn.execute(insert(timeline_event).values(**values, created_at=now, updated_at=now))
            except IntegrityError:
                # 并发写入同一件事：另一条已经落库，读回来当合并结果
                row = (await conn.execute(select(timeline_event).where(and_(
                    timeline_event.c.owner_id == values["owner_id"],
                    timeline_event.c.role_id == values["role_id"],
                    timeline_event.c.dedupe_key == values["dedupe_key"])))).mappings().first()
                if row is None:
                    raise
                return _event(row)
        return event

    async def set_status(self, *, owner_id: str, public_id: str, status: EventStatus) -> bool:
        now = _now()
        async with self._engine.begin() as conn:
            current = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.public_id == public_id,
                timeline_event.c.owner_id == int(owner_id))))).mappings().first()
            if current is None:
                return False
            event = _event(current)
            event.status = EventStatus(status)
            await conn.execute(update(timeline_event).where(timeline_event.c.id == current["id"])
                               .values(status=event.status.value, next_at_utc=None, updated_at=now))
        return True

    async def delete(self, *, owner_id: str, public_id: str) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(timeline_event).where(and_(
                timeline_event.c.public_id == public_id, timeline_event.c.owner_id == int(owner_id))))
        return res.rowcount == 1

    async def mark_stale_for_source(self, *, owner_id: str, message_id: str) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(update(timeline_event).where(and_(
                timeline_event.c.owner_id == int(owner_id),
                timeline_event.c.source_message_id == message_id,
                timeline_event.c.origin != EventOrigin.MANUAL.value,
            )).values(status=EventStatus.STALE.value, next_at_utc=None, updated_at=_now()))
        return res.rowcount

    async def delete_for_session(self, *, owner_id: str, session_id: int) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(timeline_event).where(and_(
                timeline_event.c.owner_id == int(owner_id), timeline_event.c.session_id == session_id,
                timeline_event.c.origin != EventOrigin.MANUAL.value)))
        return res.rowcount

    async def close_overdue(self, *, now: datetime, grace: timedelta, limit: int = 500) -> int:
        """分批：一次最多 ``limit`` 条，避免一个大事务锁很多行；调用方循环到返回 0。"""
        cutoff = _naive(now - grace)
        async with self._engine.begin() as conn:
            ids = (await conn.execute(select(timeline_event.c.id).where(and_(
                timeline_event.c.status == EventStatus.SCHEDULED.value,
                timeline_event.c.recurrence == Recurrence.NONE.value,
                timeline_event.c.at_utc < cutoff)).limit(limit))).scalars().all()
            if not ids:
                return 0
            res = await conn.execute(update(timeline_event).where(timeline_event.c.id.in_(ids)).values(
                status=EventStatus.MISSED.value, next_at_utc=None, updated_at=_now()))
        return res.rowcount

    async def delete_user(self, *, owner_id: str) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(timeline_event).where(timeline_event.c.owner_id == int(owner_id)))
        return res.rowcount

    # ---- 读 ----

    async def get(self, *, owner_id: str, public_id: str) -> TimelineEvent | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.public_id == public_id,
                timeline_event.c.owner_id == int(owner_id))))).mappings().first()
        return _event(row) if row else None

    async def by_source(self, *, owner_id: str, message_id: str) -> list[TimelineEvent]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.owner_id == int(owner_id),
                timeline_event.c.source_message_id == message_id)).order_by(timeline_event.c.at_utc))).mappings().all()
        return [_event(r) for r in rows]

    async def upcoming(self, *, owner_id: str, role_id: str, now: datetime, horizon: timedelta,
                       limit: int = 5) -> list[TimelineEvent]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.owner_id == int(owner_id), timeline_event.c.role_id == role_id,
                timeline_event.c.status == EventStatus.SCHEDULED.value,
                timeline_event.c.next_at_utc.isnot(None),
                timeline_event.c.next_at_utc <= _naive(now + horizon),
            )).order_by(timeline_event.c.next_at_utc).limit(limit))).mappings().all()
        return [_event(r) for r in rows]

    async def due_between(self, *, start: datetime, end: datetime, limit: int = 500) -> list[TimelineEvent]:
        """所有用户里 ``next_at_utc`` 落在 [start, end] 的未完成事件，供主动开口的调度器扫描。

        带 ``reminder_id`` 的事件排除在外：它们已经有一条提醒（``ca_reminder``）按用户要求的时间发出，
        再由这里主动开口就是同一件事通知两次。
        """
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.status == EventStatus.SCHEDULED.value,
                timeline_event.c.reminder_id.is_(None),
                timeline_event.c.next_at_utc.isnot(None),
                timeline_event.c.next_at_utc >= _naive(start),
                timeline_event.c.next_at_utc <= _naive(end),
            )).order_by(timeline_event.c.next_at_utc).limit(max(0, min(limit, 1000))))).mappings().all()
        return [_event(r) for r in rows]

    async def recent_past(self, *, owner_id: str, role_id: str, now: datetime, window: timedelta,
                          limit: int = 2) -> list[TimelineEvent]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(timeline_event).where(and_(
                timeline_event.c.owner_id == int(owner_id), timeline_event.c.role_id == role_id,
                timeline_event.c.status == EventStatus.SCHEDULED.value,
                timeline_event.c.recurrence == Recurrence.NONE.value,
                timeline_event.c.at_utc < _naive(now), timeline_event.c.at_utc >= _naive(now - window),
            )).order_by(timeline_event.c.at_utc.desc()).limit(limit))).mappings().all()
        return [_event(r) for r in rows]

    async def list_for_owner(self, *, owner_id: str, role_id: str | None = None, include_past: bool = False,
                             limit: int = 50, offset: int = 0) -> list[TimelineEvent]:
        cond = [timeline_event.c.owner_id == int(owner_id)]
        if role_id is not None:
            cond.append(timeline_event.c.role_id == role_id)
        if not include_past:
            cond.append(timeline_event.c.next_at_utc.isnot(None))
            cond.append(timeline_event.c.next_at_utc >= _now())
            cond.append(timeline_event.c.status == EventStatus.SCHEDULED.value)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(timeline_event).where(and_(*cond))
                                       .order_by(timeline_event.c.at_utc)
                                       .limit(max(0, min(limit, 100))).offset(max(0, offset)))).mappings().all()
        return [_event(r) for r in rows]
