"""事件时间线：用户什么时候会发生什么。

与事实记忆分开存储，因为两者的问题不同：

- 事实（记忆接口）：「用户喜欢安静」——长期有效，按语义检索。
- 事件（这里）：「下周三下午两点面试」——有时间锚点，按时间窗口查询，会过期、
  会被取消、会重复（生日）。

合成一个存储会让两种查询互相拖累，也让「删除」的语义变得含糊。

和聊天对齐的三件事（chat-agent-timeline-design.md）：
- 按「用户 + 角色」隔离（``user_id`` + ``source_character_id``）；
- 记下来自哪条用户消息（``source_message_id``），消息删除或编辑时能联动；
- 同一件事只留一条（``dedupe_key``）：工具记一次、回合后抽取再记一次，不会重复。
"""

from __future__ import annotations

import hashlib
import re
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


class EventOrigin(str, Enum):
    """事件从哪来。``MANUAL``（用户在记忆页手动添加）不会被消息的删除 / 编辑影响。"""

    TOOL = "tool"
    EXTRACTED = "extracted"
    MANUAL = "manual"


# 兼容旧写法（旧代码用 ``ORIGIN_MANUAL`` 这样的常量）
ORIGIN_TOOL = EventOrigin.TOOL
ORIGIN_EXTRACTED = EventOrigin.EXTRACTED
ORIGIN_MANUAL = EventOrigin.MANUAL


class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    DONE = "done"
    CANCELLED = "cancelled"
    MISSED = "missed"
    STALE = "stale"          # 来源消息被编辑或删除：保留记录，不再提起、不再触发提醒


class Recurrence(str, Enum):
    NONE = "none"
    YEARLY = "yearly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def dedupe_key(title: str, at: datetime) -> str:
    """同一件事的稳定键：标题归一化 + 当地日期。时间只差几小时的两条算同一件。"""
    normalized = re.sub(r"\s+", "", re.sub(r"[，。！？、,.!?：:'\"“”‘’()（）\[\]【】]", "", title.strip().lower()))
    if not normalized:
        normalized = title.strip().lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:24]
    return f"{digest}|{_aware(at).date().isoformat()}"


def _add_months(value: datetime, months: int) -> datetime:
    """按日历月推进；目标月没有这一天时取当月最后一天（1 月 31 日 → 2 月 28/29 日）。"""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    for day in (value.day, 30, 29, 28):
        try:
            return value.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return value.replace(year=year, month=month, day=1)


@dataclass
class TimelineEvent:
    id: str                     # 对外 id（ULID）；写入前可以是空串，由存储分配
    user_id: str
    kind: EventKind
    title: str
    at: datetime
    source_character_id: str = ""
    source_message_id: str = ""
    session_id: int | None = None
    reminder_id: int | None = None
    origin: EventOrigin = EventOrigin.EXTRACTED
    # 抽取置信度。低于驱动阈值的事件只存着供对话引用，不拿来主动打扰用户——
    # 一次误报的提醒，比少一次提醒代价大得多。
    confidence: float = 1.0
    status: EventStatus = EventStatus.SCHEDULED
    recurrence: Recurrence = Recurrence.NONE
    all_day: bool = False            # 生日、纪念日按当地日期，不按时刻
    remind_before: timedelta | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.at = _aware(self.at)
        self.kind = EventKind(self.kind)
        self.status = EventStatus(self.status)
        self.recurrence = Recurrence(self.recurrence)
        self.origin = EventOrigin(self.origin)
        if not self.id:
            self.id = uuid.uuid4().hex[:26]

    @property
    def is_recurring(self) -> bool:
        return self.recurrence != Recurrence.NONE

    @property
    def dedupe_key(self) -> str:
        return dedupe_key(self.title, self.at)

    def next_occurrence(self, *, after: datetime) -> datetime | None:
        """下一次发生时间。一次性事件返回自身时间（已过则 None）。

        ``after`` 可以是 naive（数据库读出来的本地 UTC）：统一按 UTC 比较，不要求调用方先转时区。
        """
        if self.status != EventStatus.SCHEDULED:
            return None
        after = _aware(after)
        if not self.is_recurring:
            return self.at if self.at > after else None

        # 每次都从原始时间推进，不在上一次的结果上加：1 月 31 日的每月事件
        # 不会因为二月只有 28 天，之后永远变成 28 日。
        if self.recurrence == Recurrence.WEEKLY:
            span = after - self.at
            candidate = self.at + timedelta(days=7 * (max(0, span.days) // 7 + 1))
            return candidate if candidate > after else None
        months = 12 if self.recurrence == Recurrence.YEARLY else 1
        now = after
        years = max(0, (now.year - self.at.year))
        k = years * 12 // months if months else 0
        after = _aware(after)
        # 有界循环：从估计的位置往前找，最多走 MAX_RECURRENCE_STEPS 步。
        for _ in range(MAX_RECURRENCE_STEPS):
            candidate = _add_months(self.at, months * k)
            if candidate > after:
                return candidate
            k += 1
        return None

    def next_at(self, *, now: datetime) -> datetime | None:
        """存进 ``next_at_utc`` 的值：一次性事件就是自身时间，重复事件是下一次。"""
        return self.next_occurrence(after=now)


MAX_RECURRENCE_STEPS = 1_000
