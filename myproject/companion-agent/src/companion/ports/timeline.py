from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Protocol
from companion.domain.timeline.models import EventStatus, TimelineEvent


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
