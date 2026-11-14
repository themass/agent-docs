"""首批工具（T §2.6）。handler 只依赖端口，身份来自 ToolContext，参数模型不含身份字段。

替代 app/tools/core.py（旧 ActionSpec 体系，仍被 container 引用，T13 删除）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, Field

from companion.agent.memory.subject import role_subject
from companion.service.proactive.model import local_time_text
from companion.service.timeline.models import EventKind, EventOrigin, TimelineEvent
from companion.agent.tools.registry import ToolRegistry
from companion.agent.tools.spec import Permission, SideEffect, ToolContext, ToolSpec
from companion.agent.memory.port import MemoryItem

KIND_VALUES = tuple(k.value for k in EventKind)


class NoParams(BaseModel):
    pass


class RecallMemoryParams(BaseModel):
    """一次召回同时覆盖事实与近期事件。

    以前是两个工具（recall_facts / recall_events），模型每次都要各调一遍——
    每次工具调用都要重新过一遍模型，在这套异地基础设施上每次约 2.3 秒。
    两路数据本来就互不依赖，合成一次调用不损失表达力。
    """
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=5)


class RememberFactParams(BaseModel):
    content: str = Field(min_length=2, max_length=300)


class RememberEventParams(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    at: AwareDatetime
    kind: Literal[KIND_VALUES] = "other"  # type: ignore[valid-type]


class CreateReminderParams(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="到点时要提醒用户的事，用用户的原话概括")
    at: AwareDatetime = Field(description="带时区偏移的绝对时间；先调用 get_current_time 再换算「明天下午 3 点」这类说法")
    timezone: str | None = Field(default=None, max_length=64, description="用户所在时区（IANA 名称，如 Asia/Shanghai）。用户没说过、记忆里也没有时，先问一句，不要默认 UTC")


class CancelReminderParams(BaseModel):
    reminder_id: int = Field(ge=1)


RECALL_HORIZON = timedelta(days=14)


def register_builtin_tools(registry: ToolRegistry, *, memory: Any, timeline: Any,
                           clock: Callable[[], datetime] = lambda: datetime.now(UTC),
                           reminders: Any = None) -> None:
    """``reminders``：app/proactive/reminders.ReminderService。给了它，create_reminder 会建服务端提醒，
    到点由服务端主动联系用户；不给则退回旧行为（只记时间线，通知由端上调度）。"""

    async def get_current_time(ctx: ToolContext, args: NoParams) -> dict[str, str]:
        return {"now": clock().isoformat(), "timezone": "UTC"}

    def subject(ctx: ToolContext) -> str:
        # 记忆按角色隔离：工具只看得到、只写得进当前角色的记忆空间。
        return role_subject(ctx.owner_id, ctx.character_id or None)

    async def recall_memory(ctx: ToolContext, args: RecallMemoryParams) -> dict[str, Any]:
        """事实记忆与近期事件一起返回。

        两路并发：memory.search 走库、timeline.upcoming 也走库，但它们互不依赖。
        串行在这套异地数据库上是白白多付一次往返（实测单次约 180 ms）。
        任一路失败只让那一路为空，不拖累另一路——记忆读不到不该让回合说不出话。
        """
        facts, events = await asyncio.gather(
            memory.search(subject(ctx), args.query, limit=args.limit),
            timeline.upcoming(owner_id=str(ctx.owner_id), role_id=ctx.character_id,
                              now=clock(), horizon=RECALL_HORIZON, limit=args.limit),
            return_exceptions=True,
        )
        out: dict[str, Any] = {"facts": [], "events": []}
        if not isinstance(facts, BaseException):
            out["facts"] = [{"content": i.content} for i in facts]
        if not isinstance(events, BaseException):
            out["events"] = [{"title": e.title, "at": e.at.isoformat(), "kind": e.kind.value}
                             for e in events]
        return out

    async def remember_fact(ctx: ToolContext, args: RememberFactParams) -> dict[str, str]:
        item = MemoryItem(id=uuid4().hex, content=args.content, source_character_id=ctx.character_id)
        await memory.add(subject(ctx), [item])
        return {"saved": "fact"}

    async def remember_event(ctx: ToolContext, args: RememberEventParams) -> dict[str, str]:
        event = TimelineEvent(
            id="", user_id=str(ctx.owner_id), kind=EventKind(args.kind), title=args.title, at=args.at,
            source_character_id=ctx.character_id, session_id=ctx.session_id, origin=EventOrigin.TOOL,
            confidence=0.8)
        saved = await timeline.upsert(event)
        return {"event_id": saved.id, "at": saved.at.isoformat()}

    async def create_reminder(ctx: ToolContext, args: CreateReminderParams) -> dict[str, str]:
        """只在用户确认后执行。同一确认重复执行只建一条（按 confirmation_id 幂等）。"""
        event = TimelineEvent(
            id="", user_id=str(ctx.owner_id), kind=EventKind.OTHER, title=args.title, at=args.at,
            source_character_id=ctx.character_id, session_id=ctx.session_id, origin=EventOrigin.TOOL,
            confidence=1.0, remind_before=timedelta(minutes=30))
        if reminders is None:
            saved = await timeline.upsert(event)
            return {"event_id": saved.id, "remind_before_minutes": "30"}
        record = await reminders.create(owner_id=ctx.owner_id, session_id=ctx.session_id, at=args.at,
                                        timezone=args.timezone, content=args.title,
                                        confirmation_id=ctx.confirmation_id)
        # 时间线也记一笔：之后的对话能自然地提起这件事（同一件事只留一条）
        await timeline.upsert(replace(event, reminder_id=record.id))
        return {"reminder_id": str(record.id), "due_local": local_time_text(record.due_at, record.timezone),
                "timezone": record.timezone}

    async def list_reminders(ctx: ToolContext, args: NoParams) -> list[dict[str, str]]:
        items = await reminders.list(owner_id=ctx.owner_id)
        return [{"reminder_id": str(r.id), "content": r.content,
                 "due_local": local_time_text(r.due_at, r.timezone)} for r in items]

    async def cancel_reminder(ctx: ToolContext, args: CancelReminderParams) -> dict[str, str]:
        ok = await reminders.cancel(owner_id=ctx.owner_id, reminder_id=args.reminder_id)
        return {"cancelled": "true" if ok else "false"}

    registry.register(ToolSpec(
        name="get_current_time", description="返回当前时间（UTC，不是用户本地时间）。需要判断今天、明天、星期几时调用，不要猜日期；换算成用户本地时间要先知道他的时区。",
        params=NoParams, permission=Permission.READ, side_effect=SideEffect.NONE, result_budget_chars=200,
    ), get_current_time)
    registry.register(ToolSpec(
        name="recall_memory",
        description="回忆用户说过的事：事实记忆（喜好、职业、家人、反复出现的困扰）与近期的重要日子"
                    "（面试、生日、约定）。需要引用他之前提过的事时调用，不要凭印象编。一次调用同时返回两类。",
        params=RecallMemoryParams, permission=Permission.READ, side_effect=SideEffect.NONE,
    ), recall_memory)
    registry.register(ToolSpec(
        name="remember_fact", description="用户明确要求「记住」某件事时调用。用户可以在记忆页删除。",
        params=RememberFactParams, permission=Permission.AUTO, side_effect=SideEffect.OWN_DATA,
    ), remember_fact)
    registry.register(ToolSpec(
        name="remember_event", description="用户陈述了带时间点的事件（面试、生日、复诊、考试）时调用。只记用户明确说过的。",
        params=RememberEventParams, permission=Permission.AUTO, side_effect=SideEffect.OWN_DATA,
    ), remember_event)
    registry.register(ToolSpec(
        name="create_reminder",
        description="用户请你在某个时间提醒他、联系他（如「明天下午 3 点叫我开会」）时调用。到点后你会主动联系用户。"
                    "会触达用户，必须经用户确认。",
        params=CreateReminderParams, permission=Permission.CONFIRM, side_effect=SideEffect.EXTERNAL,
        confirm_title="建立提醒", products=frozenset({"roleplay", "chat"}),
    ), create_reminder)
    if reminders is not None:
        registry.register(ToolSpec(
            name="list_reminders", description="查看用户还没到时间的提醒。",
            params=NoParams, permission=Permission.READ, side_effect=SideEffect.NONE,
            products=frozenset({"roleplay", "chat"}),
        ), list_reminders)
        registry.register(ToolSpec(
            name="cancel_reminder", description="用户明确要求取消某条提醒时调用（先用 list_reminders 找到它）。",
            params=CancelReminderParams, permission=Permission.AUTO, side_effect=SideEffect.OWN_DATA,
            products=frozenset({"roleplay", "chat"}),
        ), cancel_reminder)
