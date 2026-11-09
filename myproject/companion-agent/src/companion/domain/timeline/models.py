"""事件时间线：用户什么时候会发生什么。

与事实记忆分开存储，因为两者的问题不同：

- 事实（mem0）：「用户喜欢安静」——长期有效，按语义检索。
- 事件（这里）：「下周三下午两点面试」——有时间锚点，按时间窗口查询，会过期、
  会被取消、会重复（生日）。

合成一个存储会让两种查询互相拖累，也让「删除」的语义变得含糊。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum


class EventKind(str, Enum):
    INTERVIEW = "interview"
    BIRTHDAY = "birthday"
    EXAM = "exam"
    APPOINTMENT = "appointment"
    ANNIVERSARY = "anniversary"
    TRIP = "trip"
    OTHER = "other"


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    DONE = "done"
    CANCELLED = "cancelled"
    MISSED = "missed"


class Recurrence(str, Enum):
    NONE = "none"
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class TimelineEvent:
    id: str
    user_id: str
    kind: EventKind
    title: str
    at: datetime
    source_character_id: str = ""
    source_message_id: str = ""
    # 抽取置信度。低于驱动阈值的事件只存着供对话引用，不拿来主动打扰用户——
    # 一次误报的提醒，比少一次提醒代价大得多。
    confidence: float = 1.0
    status: EventStatus = EventStatus.SCHEDULED
    recurrence: Recurrence = Recurrence.NONE
    remind_before: timedelta | None = None
    created_at: datetime = field(default_factory=utc_now)

    @property
    def is_recurring(self) -> bool:
        return self.recurrence != Recurrence.NONE

    def next_occurrence(self, *, after: datetime) -> datetime | None:
        """下一次发生时间。一次性事件返回自身时间（已过则 None）。"""
        if self.status != EventStatus.SCHEDULED:
            return None
        if not self.is_recurring:
            return self.at if self.at > after else None

        candidate = self.at
        step = {
            Recurrence.YEARLY: lambda d: d.replace(year=d.year + 1),
            Recurrence.MONTHLY: lambda d: d + timedelta(days=30),
            Recurrence.WEEKLY: lambda d: d + timedelta(days=7),
        }[self.recurrence]
        # 有界循环：一个 1990 年的生日不该让这里转上千万次。
        for _ in range(MAX_RECURRENCE_STEPS):
            if candidate > after:
                return candidate
            candidate = step(candidate)
        return None


MAX_RECURRENCE_STEPS = 1_000
