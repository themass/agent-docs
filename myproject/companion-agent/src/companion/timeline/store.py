"""时间线的存取。

接口与实现分开的理由同记忆层：现在用内存，将来换数据库；上层只认 [TimelinePort]。
查询以**时间窗口**为主——这是事件与事实最本质的区别。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol

from companion.timeline.models import EventStatus, TimelineEvent


class TimelinePort(Protocol):
    async def add(self, event: TimelineEvent) -> TimelineEvent: ...

    async def update_status(
        self, user_id: str, event_id: str, status: EventStatus
    ) -> bool: ...

    async def delete_one(self, user_id: str, event_id: str) -> bool: ...

    async def delete_user(self, user_id: str) -> int: ...

    async def list_for_user(
        self, user_id: str, *, limit: int = 50, include_past: bool = False
    ) -> list[TimelineEvent]: ...

    async def due_between(
        self, *, start: datetime, end: datetime
    ) -> list[TimelineEvent]: ...


class InMemoryTimeline:
    """dict + 锁。进程内有效，重启即丢；测试与本地开发够用。"""

    def __init__(self) -> None:
        self._items: dict[str, TimelineEvent] = {}
        self._lock = asyncio.Lock()

    async def add(self, event: TimelineEvent) -> TimelineEvent:
        async with self._lock:
            self._items[event.id] = event
        return event

    async def update_status(
        self, user_id: str, event_id: str, status: EventStatus
    ) -> bool:
        async with self._lock:
            event = self._items.get(event_id)
            # 用户隔离在写入层强制：拿到别人的 id 也改不了。
            if event is None or event.user_id != user_id:
                return False
            event.status = status
            return True

    async def delete_one(self, user_id: str, event_id: str) -> bool:
        async with self._lock:
            event = self._items.get(event_id)
            if event is None or event.user_id != user_id:
                return False
            del self._items[event_id]
            return True

    async def delete_user(self, user_id: str) -> int:
        async with self._lock:
            doomed = [k for k, v in self._items.items() if v.user_id == user_id]
            for key in doomed:
                del self._items[key]
            return len(doomed)

    async def list_for_user(
        self, user_id: str, *, limit: int = 50, include_past: bool = False
    ) -> list[TimelineEvent]:
        async with self._lock:
            items = [e for e in self._items.values() if e.user_id == user_id]
        if not include_past:
            cutoff = datetime.now(UTC)
            items = [e for e in items if e.at >= cutoff]
        items.sort(key=lambda e: e.at)
        return items[:limit]

    async def due_between(
        self, *, start: datetime, end: datetime
    ) -> list[TimelineEvent]:
        """取窗口内到期的事件。

        重复事件要按这一次的发生时间算，不能只看 `at` 原始值——否则一个 1990 年
        的生日永远不会被扫到。
        """
        async with self._lock:
            items = list(self._items.values())
        due: list[TimelineEvent] = []
        for event in items:
            occurrence = event.next_occurrence(after=start - timedelta(seconds=1))
            if occurrence is None:
                continue
            if start <= occurrence <= end:
                due.append(event)
        due.sort(key=lambda e: e.at)
        return due

    async def aclose(self) -> None:
        return None
