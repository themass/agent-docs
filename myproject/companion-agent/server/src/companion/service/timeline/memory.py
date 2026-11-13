"""时间线的进程内实现：测试与本地开发用。语义与 ``SqlTimelineStore`` 一致（同一份协议）。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from companion.service.timeline.models import EventOrigin, EventStatus, TimelineEvent

# 「现在」的判断统一用它，避免 naive / aware 混用
def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class InMemoryTimeline:
    """dict + 锁。重启即丢；多副本互不可见。生产用 SqlTimelineStore。"""

    def __init__(self) -> None:
        self._items: dict[str, TimelineEvent] = {}
        self._lock = asyncio.Lock()

    # ---- 写 ----

    async def upsert(self, event: TimelineEvent) -> TimelineEvent:
        async with self._lock:
            for existing in self._items.values():
                if (existing.user_id, existing.source_character_id, existing.dedupe_key) == \
                        (event.user_id, event.source_character_id, event.dedupe_key):
                    # 合并：保留 id 与来源，补全更可信的信息
                    existing.at = event.at
                    existing.confidence = max(existing.confidence, event.confidence)
                    if event.reminder_id is not None:
                        existing.reminder_id = event.reminder_id
                    if event.source_message_id:
                        existing.source_message_id = event.source_message_id
                    if event.status == EventStatus.SCHEDULED and existing.status == EventStatus.STALE:
                        existing.status = EventStatus.SCHEDULED
                    return existing
            self._items[event.id] = event
            return event

    async def add(self, event: TimelineEvent) -> TimelineEvent:      # 旧名字，等同 upsert
        return await self.upsert(event)

    async def set_status(self, *, owner_id: str, public_id: str, status: EventStatus) -> bool:
        async with self._lock:
            event = self._items.get(public_id)
            if event is None or event.user_id != owner_id:
                return False
            event.status = EventStatus(status)
            return True

    async def update_status(self, user_id: str, event_id: str, status: EventStatus) -> bool:  # 旧名字
        return await self.set_status(owner_id=user_id, public_id=event_id, status=status)

    async def delete(self, *, owner_id: str, public_id: str) -> bool:
        async with self._lock:
            event = self._items.get(public_id)
            if event is None or event.user_id != owner_id:
                return False
            del self._items[public_id]
            return True

    async def delete_one(self, user_id: str, event_id: str) -> bool:    # 旧名字
        return await self.delete(owner_id=user_id, public_id=event_id)

    async def mark_stale_for_source(self, *, owner_id: str, message_id: str) -> int:
        async with self._lock:
            hits = [e for e in self._items.values()
                    if e.user_id == owner_id and e.source_message_id == message_id
                    and e.origin != EventOrigin.MANUAL]
            for event in hits:
                event.status = EventStatus.STALE
            return len(hits)

    async def delete_for_session(self, *, owner_id: str, session_id: int) -> int:
        async with self._lock:
            doomed = [k for k, e in self._items.items()
                      if e.user_id == owner_id and e.session_id == session_id and e.origin != EventOrigin.MANUAL]
            for key in doomed:
                del self._items[key]
            return len(doomed)

    async def close_overdue(self, *, now: datetime, grace: timedelta, limit: int = 500) -> int:
        cutoff = _aware(now) - grace
        async with self._lock:
            hits = [e for e in self._items.values()
                    if e.status == EventStatus.SCHEDULED and not e.is_recurring and e.at < cutoff][:limit]
            for event in hits:
                event.status = EventStatus.MISSED
            return len(hits)

    async def delete_user(self, owner_id: str | None = None, *, user_id: str | None = None) -> int:
        owner_id = owner_id or user_id or ""
        async with self._lock:
            doomed = [k for k, e in self._items.items() if e.user_id == owner_id]
            for key in doomed:
                del self._items[key]
            return len(doomed)

    # ---- 读 ----

    async def list_for_owner(self, *, owner_id: str, role_id: str | None = None, include_past: bool = False,
                             limit: int = 50, offset: int = 0) -> list[TimelineEvent]:
        return await self.list_for_user(owner_id, role_id=role_id, include_past=include_past,
                                        limit=limit, offset=offset)

    async def get(self, *, owner_id: str, public_id: str) -> TimelineEvent | None:
        async with self._lock:
            event = self._items.get(public_id)
        return event if event is not None and event.user_id == owner_id else None

    async def by_source(self, *, owner_id: str, message_id: str) -> list[TimelineEvent]:
        async with self._lock:
            hits = [e for e in self._items.values()
                    if e.user_id == owner_id and e.source_message_id == message_id]
        hits.sort(key=lambda e: e.at)
        return hits

    def _next(self, event: TimelineEvent, now: datetime) -> datetime | None:
        if event.status != EventStatus.SCHEDULED:
            return None
        return event.next_occurrence(after=now)

    async def upcoming(self, *, owner_id: str, role_id: str, now: datetime, horizon: timedelta,
                       limit: int = 5) -> list[TimelineEvent]:
        async with self._lock:
            items = [e for e in self._items.values()
                     if e.user_id == owner_id and e.source_character_id == role_id]
        now = _aware(now)
        out = [(nxt, e) for e in items if (nxt := self._next(e, now)) is not None and nxt <= now + horizon]
        out.sort(key=lambda p: p[0])
        return [e for _, e in out[:limit]]

    async def recent_past(self, *, owner_id: str, role_id: str, now: datetime, window: timedelta,
                          limit: int = 2) -> list[TimelineEvent]:
        async with self._lock:
            items = [e for e in self._items.values()
                     if e.user_id == owner_id and e.source_character_id == role_id]
        now = _aware(now)
        out = [e for e in items
               if e.status == EventStatus.SCHEDULED and not e.is_recurring and now - window <= e.at < now]
        out.sort(key=lambda e: e.at, reverse=True)
        return out[:limit]

    async def list_for_user(self, owner_id: str | None = None, *, user_id: str | None = None,
                            role_id: str | None = None, include_past: bool = False,
                            limit: int = 50, offset: int = 0) -> list[TimelineEvent]:
        # 旧调用方（旧栈的记忆页与召回中间件）按位置传 user_id；新代码一律用 owner_id。
        owner_id = owner_id or user_id or ""
        async with self._lock:
            items = [e for e in self._items.values()
                     if e.user_id == owner_id and (role_id is None or e.source_character_id == role_id)]
        if not include_past:
            # 与 SQL 实现一致：只看将来、仍为 scheduled 的（完成 / 取消 / 作废的不再出现）
            cutoff = datetime.now(UTC)
            items = [e for e in items if e.at >= cutoff and e.status == EventStatus.SCHEDULED]
        items.sort(key=lambda e: e.at)
        return items[offset:offset + limit]

    async def due_between(self, *, start: datetime, end: datetime) -> list[TimelineEvent]:
        """旧接口：窗口内到期的事件。新栈的提醒走 ca_reminder，这里只为兼容旧调度器保留。"""
        async with self._lock:
            items = list(self._items.values())
        due: list[TimelineEvent] = []
        for event in items:
            occurrence = event.next_occurrence(after=start - timedelta(seconds=1))
            if occurrence is not None and start <= occurrence <= end:
                due.append(event)
        due.sort(key=lambda e: e.at)
        return due

    async def aclose(self) -> None:
        return None
