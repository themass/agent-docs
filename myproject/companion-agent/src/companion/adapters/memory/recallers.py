"""记忆 hook 的适配器：把现有的记忆端口与时间线接成 Recaller / Forgetter。

后端可以随意替换：只要实现 ``MemoryPort``（chat-agent-memory-spec.md）或 ``TimelinePort``，
这里的适配器不用改；换成别的检索服务，就再写一个 Recaller。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from companion.domain.memory.hooks import RecallQuery, RecallResult, RecalledItem
from companion.domain.memory.subject import role_subject

SCHEDULED = "scheduled"


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


class MemoryPortRecaller:
    """长期记忆（事实、偏好、事件）。``port`` 是作用域客户端（memory_hub 的 ScopedMemory）。

    ``per_role``：按角色隔离（默认）。查询带 role_id 时只查该角色的记忆主体（domain/memory/subject.py）。
    """

    def __init__(self, port: Any, *, name: str = "facts", per_role: bool = True) -> None:
        self._port = port
        self.name = name
        self._per_role = per_role

    async def recall(self, query: RecallQuery) -> RecallResult:
        subject = role_subject(query.user_id, query.role_id) if self._per_role else query.user_id
        try:
            items = await self._port.search(subject, query.text, limit=query.limit)
        except Exception as exc:  # noqa: BLE001 —— 协议要求不抛
            return RecallResult(source=self.name, error=type(exc).__name__)
        out: list[RecalledItem] = []
        for item in items:
            occurred = _naive_utc(getattr(item, "created_at", None))
            if query.occurred_before is not None and occurred is not None and occurred >= query.occurred_before:
                continue
            kind = str(getattr(getattr(item, "kind", None), "value", "fact")).lower()
            out.append(RecalledItem(
                text=item.content, source=self.name, ref=str(item.id), occurred_at=occurred,
                score=getattr(item, "score", None), tags=frozenset({"event" if kind == "event" else "fact"})))
        return RecallResult(source=self.name, items=tuple(out), truncated=len(items) >= query.limit)


class TimelineRecaller:
    """时间线：只取将来、未完成的事件（过去的不提，避免「你上周那个面试」这种已过时的话）。

    ``per_role``：只取当前角色记下的事件（与记忆一样按角色隔离）。
    """

    def __init__(self, timeline: Any, *, name: str = "timeline", per_role: bool = True) -> None:
        self._timeline = timeline
        self.name = name
        self._per_role = per_role

    async def recall(self, query: RecallQuery) -> RecallResult:
        try:
            events = await self._timeline.list_for_user(query.user_id, limit=query.limit)
        except Exception as exc:  # noqa: BLE001
            return RecallResult(source=self.name, error=type(exc).__name__)
        out: list[RecalledItem] = []
        for event in events:
            if getattr(getattr(event, "status", None), "value", "") != SCHEDULED:
                continue
            if self._per_role and query.role_id and getattr(event, "source_character_id", "") != query.role_id:
                continue
            at = _naive_utc(getattr(event, "at", None))
            when = at.strftime("%m-%d %H:%M") if at else ""
            out.append(RecalledItem(text=f"{when} {event.title}".strip(), source=self.name, ref=str(event.id),
                                    occurred_at=at, tags=frozenset({"event"})))
        return RecallResult(source=self.name, items=tuple(out))


class MemoryPortForgetter:
    """``user_id`` 由调用方给出记忆主体（按角色隔离时用 role_subject）。"""

    def __init__(self, port: Any, *, name: str = "facts") -> None:
        self._port = port
        self.name = name

    async def forget(self, *, scope: str, user_id: str, ref: str | None) -> int:
        if ref is None:
            return await self._port.delete_user(user_id)
        return 1 if await self._port.delete_one(user_id, ref) else 0
