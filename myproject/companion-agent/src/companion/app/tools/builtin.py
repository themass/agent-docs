"""首批工具（T §2.6）。handler 只依赖端口，身份来自 ToolContext，参数模型不含身份字段。

替代 app/tools/core.py（旧 ActionSpec 体系，仍被 container 引用，T13 删除）。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, Field

from companion.domain.timeline.models import EventKind, TimelineEvent
from companion.domain.tools.registry import ToolRegistry
from companion.domain.tools.spec import Permission, SideEffect, ToolContext, ToolSpec
from companion.ports.memory import MemoryItem

KIND_VALUES = tuple(k.value for k in EventKind)


class NoParams(BaseModel):
    pass


class RecallFactsParams(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=5)


class RecallEventsParams(BaseModel):
    limit: int = Field(default=5, ge=1, le=10)


class RememberFactParams(BaseModel):
    content: str = Field(min_length=2, max_length=300)


class RememberEventParams(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    at: AwareDatetime
    kind: Literal[KIND_VALUES] = "other"  # type: ignore[valid-type]


class CreateReminderParams(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    at: AwareDatetime


def register_builtin_tools(registry: ToolRegistry, *, memory: Any, timeline: Any,
                           clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:

    async def get_current_time(ctx: ToolContext, args: NoParams) -> dict[str, str]:
        return {"now": clock().isoformat(), "timezone": "UTC"}

    async def recall_facts(ctx: ToolContext, args: RecallFactsParams) -> list[dict[str, str]]:
        items = await memory.search(str(ctx.owner_id), args.query, limit=args.limit)
        return [{"content": i.content} for i in items]

    async def remember_fact(ctx: ToolContext, args: RememberFactParams) -> dict[str, str]:
        item = MemoryItem(id=uuid4().hex, content=args.content, source_character_id=ctx.character_id)
        await memory.add(str(ctx.owner_id), [item])
        return {"saved": "fact"}

    async def recall_events(ctx: ToolContext, args: RecallEventsParams) -> list[dict[str, str]]:
        events = await timeline.list_for_user(str(ctx.owner_id), limit=args.limit)
        return [{"title": e.title, "at": e.at.isoformat(), "kind": e.kind.value} for e in events]

    async def remember_event(ctx: ToolContext, args: RememberEventParams) -> dict[str, str]:
        event = TimelineEvent(
            id=uuid4().hex, user_id=str(ctx.owner_id), kind=EventKind(args.kind), title=args.title,
            at=args.at, source_character_id=ctx.character_id, confidence=0.8)
        await timeline.add(event)
        return {"event_id": event.id, "at": event.at.isoformat()}

    async def create_reminder(ctx: ToolContext, args: CreateReminderParams) -> dict[str, str]:
        """在时间线上建提醒；系统通知由端上调度。只在用户确认后执行。"""
        event = TimelineEvent(
            id=uuid4().hex, user_id=str(ctx.owner_id), kind=EventKind.OTHER, title=args.title, at=args.at,
            source_character_id=ctx.character_id, confidence=1.0, remind_before=timedelta(minutes=30))
        await timeline.add(event)
        return {"event_id": event.id, "remind_before_minutes": "30"}

    registry.register(ToolSpec(
        name="get_current_time", description="返回当前时间（UTC）。需要判断今天、明天、星期几时调用，不要猜日期。",
        params=NoParams, permission=Permission.READ, side_effect=SideEffect.NONE, result_budget_chars=200,
    ), get_current_time)
    registry.register(ToolSpec(
        name="recall_facts", description="按语义查用户的事实记忆（喜好、职业、家人、反复出现的困扰），最多 5 条。",
        params=RecallFactsParams, permission=Permission.READ, side_effect=SideEffect.NONE,
    ), recall_facts)
    registry.register(ToolSpec(
        name="recall_events", description="查用户近期的重要日子（面试、生日、约定）。",
        params=RecallEventsParams, permission=Permission.READ, side_effect=SideEffect.NONE,
    ), recall_events)
    registry.register(ToolSpec(
        name="remember_fact", description="用户明确要求「记住」某件事时调用。用户可以在记忆页删除。",
        params=RememberFactParams, permission=Permission.AUTO, side_effect=SideEffect.OWN_DATA,
    ), remember_fact)
    registry.register(ToolSpec(
        name="remember_event", description="用户陈述了带时间点的事件（面试、生日、复诊、考试）时调用。只记用户明确说过的。",
        params=RememberEventParams, permission=Permission.AUTO, side_effect=SideEffect.OWN_DATA,
    ), remember_event)
    registry.register(ToolSpec(
        name="create_reminder", description="为用户建一条提醒（会触达用户，必须经用户确认）。",
        params=CreateReminderParams, permission=Permission.CONFIRM, side_effect=SideEffect.EXTERNAL,
        confirm_title="建立提醒", products=frozenset({"roleplay"}),
    ), create_reminder)
