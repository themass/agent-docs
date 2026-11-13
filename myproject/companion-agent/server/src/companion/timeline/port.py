"""时间线存储协议（chat-agent-timeline-design.md §4）。

和记忆、提醒一样按「用户 + 角色」隔离，没有进程内状态：API 与 worker 读到的是同一份。
所有写入按 ``dedupe_key`` 幂等（同一件事只留一条），所有删除按归属校验。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from companion.timeline.models import EventStatus, TimelineEvent


class TimelineStore(Protocol):
    async def upsert(self, event: TimelineEvent) -> TimelineEvent:
        """按 ``dedupe_key`` 写入或合并：已有同角色、同一天、同标题的一条时只补全字段（id 不变）。"""
        ...

    async def get(self, *, owner_id: str, public_id: str) -> TimelineEvent | None: ...

    async def upcoming(self, *, owner_id: str, role_id: str, now: datetime, horizon: timedelta,
                       limit: int = 5) -> list[TimelineEvent]:
        """将来（含已过期但状态仍为 scheduled 的最近一段之外的）要发生的事，按时间升序。"""
        ...

    async def recent_past(self, *, owner_id: str, role_id: str, now: datetime, window: timedelta,
                          limit: int = 2) -> list[TimelineEvent]:
        """刚过去、还不知道结果的事，按时间降序。"""
        ...

    async def list_for_owner(self, *, owner_id: str, role_id: str | None = None, include_past: bool = False,
                             limit: int = 50, offset: int = 0) -> list[TimelineEvent]: ...

    async def set_status(self, *, owner_id: str, public_id: str, status: EventStatus) -> bool: ...

    async def delete(self, *, owner_id: str, public_id: str) -> bool: ...

    async def by_source(self, *, owner_id: str, message_id: str) -> list[TimelineEvent]: ...

    async def mark_stale_for_source(self, *, owner_id: str, message_id: str) -> int:
        """来源消息被删除或编辑：由它得来（非手动添加）的事件置 stale。返回条数。"""
        ...

    async def delete_for_session(self, *, owner_id: str, session_id: int) -> int:
        """会话被物理删除时清掉来源是该会话、且手动添加之外的事件。"""
        ...

    async def close_overdue(self, *, now: datetime, grace: timedelta, limit: int = 500) -> int:
        """一次性、仍为 scheduled、发生时间已超过 ``grace`` 的事件置 missed。返回条数。
        重复事件不动（它们有下一次）。"""
        ...

    async def delete_user(self, *, owner_id: str) -> int: ...
