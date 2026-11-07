"""第一批动作：记忆与时间线相关的读写。

这一批的共同点是**只碰我们自己的数据**，没有外部副作用，所以能先上。发提醒、
打电话这类会触达外部世界的动作，等确认流程在端上跑通后再接。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from companion.actions.executor import ActionRegistry, ActionSpec, Permission
from companion.timeline.models import EventKind, TimelineEvent


def register_core_actions(
    *,
    registry: ActionRegistry,
    memory: Any,
    timeline: Any,
    now: datetime | None = None,
) -> None:
    """把核心动作注册进 registry。依赖注入，测试时传内存实现。"""

    def current_time() -> datetime:
        return now or datetime.now(UTC)

    async def remember_event(
        *,
        user_id: str,
        character_id: str,
        title: str,
        at: str,
        kind: str = "other",
        recurrence: str = "none",
        confidence: float = 0.8,
    ) -> dict:
        event = TimelineEvent(
            id=f"evt-manual-{len(title)}-{at}",
            user_id=user_id,
            kind=EventKind(kind) if kind in EventKind._value2member_map_ else EventKind.OTHER,
            title=title[:60],
            at=datetime.fromisoformat(at.replace("Z", "+00:00")),
            source_character_id=character_id,
            confidence=confidence,
        )
        await timeline.add(event)
        return {"event_id": event.id, "at": event.at.isoformat()}

    async def recall_events(*, user_id: str, limit: int = 5) -> list[dict]:
        events = await timeline.list_for_user(user_id, limit=limit)
        return [
            {"title": e.title, "at": e.at.isoformat(), "kind": e.kind.value}
            for e in events
        ]

    async def recall_facts(*, user_id: str, query: str, limit: int = 5) -> list[dict]:
        items = await memory.search(user_id, query, limit=limit)
        return [{"content": i.content, "kind": getattr(i.kind, "value", str(i.kind))} for i in items]

    async def create_reminder(*, user_id: str, title: str, at: str) -> dict:
        """在时间线上建一条提醒事件。真正的系统通知由端上调度。"""
        remind_at = datetime.fromisoformat(at.replace("Z", "+00:00"))
        event = TimelineEvent(
            id=f"evt-remind-{len(title)}-{at}",
            user_id=user_id,
            kind=EventKind.OTHER,
            title=title[:60],
            at=remind_at,
            remind_before=timedelta(minutes=30),
            confidence=1.0,
        )
        await timeline.add(event)
        return {"event_id": event.id, "remind_before_minutes": 30}

    registry.register(
        ActionSpec(
            name="remember_event",
            description="记下用户明确说出的、带时间点的事件（面试、生日、复诊、考试）。只在用户陈述事实时调用。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "不超过 20 字"},
                    "at": {"type": "string", "description": "ISO8601 时间，含时区"},
                    "kind": {
                        "type": "string",
                        "enum": [k.value for k in EventKind],
                    },
                    "recurrence": {
                        "type": "string",
                        "enum": ["none", "yearly", "monthly", "weekly"],
                    },
                },
                "required": ["title", "at"],
            },
            # 写自己的库、可删、无外部副作用，所以自动执行并事后告知。
            permission=Permission.AUTO,
        ),
        remember_event,
    )

    registry.register(
        ActionSpec(
            name="recall_events",
            description="查用户近期的事件（面试、生日、约定）。需要提到用户将要发生的事时先查这里。",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            permission=Permission.READ,
        ),
        recall_events,
    )

    registry.register(
        ActionSpec(
            name="recall_facts",
            description="按语义查用户的事实记忆（喜好、职业、家人、反复出现的困扰）。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
            permission=Permission.READ,
        ),
        recall_facts,
    )

    registry.register(
        ActionSpec(
            name="create_reminder",
            description="为用户建一条提醒。会触达用户，所以必须经用户确认。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "at": {"type": "string", "description": "ISO8601 时间"},
                },
                "required": ["title", "at"],
            },
            permission=Permission.CONFIRM,
        ),
        create_reminder,
    )
