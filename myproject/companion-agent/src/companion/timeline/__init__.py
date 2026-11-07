"""事件时间线。

与事实记忆分开：事实是「他是谁」，事件是「他什么时候会发生什么」。两者的检索
方式（语义 vs 时间窗口）、生命周期（长期 vs 会过期）与删除语义都不同。
"""

from companion.timeline.extraction import extract_events, parse_events
from companion.timeline.models import (
    EventKind,
    EventStatus,
    Recurrence,
    TimelineEvent,
)
from companion.timeline.store import InMemoryTimeline, TimelinePort

__all__ = [
    "EventKind",
    "EventStatus",
    "InMemoryTimeline",
    "Recurrence",
    "TimelineEvent",
    "TimelinePort",
    "extract_events",
    "parse_events",
]
