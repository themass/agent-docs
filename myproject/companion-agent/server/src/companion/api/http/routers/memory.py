"""记忆与事件接口：用户查看、删除她被记住的东西。

这不是可选功能，是隐私要求：用户必须能看到系统记住了什么，并且能删掉。
所以这里的分页、用户隔离与删除语义都要比一般接口更严格。
"""


import logging
from typing import Any

from companion.domain.timeline.models import EventKind, EventStatus, TimelineEvent

logger = logging.getLogger(__name__)

MAX_PAGE = 100
DEFAULT_PAGE = 20


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(limit, MAX_PAGE)), max(0, offset)


class MemoryApi:
    """纯逻辑，不依赖 fastapi。用户隔离在每个方法上强制。"""

    def __init__(self, *, memory: Any, timeline: Any) -> None:
        self._memory = memory
        self._timeline = timeline

    async def list_facts(self, user_id: str, *, limit: int = DEFAULT_PAGE, offset: int = 0):
        limit, offset = _clamp(limit, offset)
        # 多取一条用来判断还有没有下一页，不给客户端一个「看起来到底了」的假象。
        items = await self._memory.list_for_user(user_id, limit=limit + 1, offset=offset)
        return items[:limit], len(items) > limit

    async def delete_fact(self, user_id: str, memory_id: str) -> bool:
        return await self._memory.delete_one(user_id, memory_id)

    async def list_events(
        self, user_id: str, *, limit: int = DEFAULT_PAGE, include_past: bool = False
    ):
        limit, _ = _clamp(limit, 0)
        return await self._timeline.list_for_user(
            user_id, limit=limit, include_past=include_past
        )

    async def add_event(
        self, user_id: str, *, title: str, at: Any, kind: str = "other"
    ) -> TimelineEvent:
        event = TimelineEvent(
            id=f"evt-user-{user_id}-{int(at.timestamp())}",
            user_id=user_id,
            kind=EventKind(kind) if kind in EventKind._value2member_map_ else EventKind.OTHER,
            title=title[:60],
            at=at,
            # 用户手动加的，可信度最高——主动提醒不会因为它被拦。
            confidence=1.0,
        )
        return await self._timeline.add(event)

    async def set_status(self, user_id: str, event_id: str, status: str) -> bool:
        if status not in EventStatus._value2member_map_:
            raise ValueError(f"unknown status: {status}")
        return await self._timeline.update_status(user_id, event_id, EventStatus(status))

    async def delete_event(self, user_id: str, event_id: str) -> bool:
        return await self._timeline.delete_one(user_id, event_id)


def build_router(api: MemoryApi, current_user: Any):
    from datetime import datetime

    from fastapi import APIRouter, Depends, HTTPException, Query
    from pydantic import BaseModel, Field

    class FactOut(BaseModel):
        id: str
        content: str
        kind: str
        source_character_id: str
        created_at: datetime

    class FactPage(BaseModel):
        items: list[FactOut]
        has_more: bool

    class EventOut(BaseModel):
        id: str
        title: str
        kind: str
        at: datetime
        status: str
        confidence: float

    class EventIn(BaseModel):
        title: str = Field(min_length=1, max_length=60)
        at: datetime
        kind: str = "other"

    router = APIRouter(prefix="/companion", tags=["companion"])

    @router.get("/memory", response_model=FactPage)
    async def list_memory(
        limit: int = Query(DEFAULT_PAGE, ge=1, le=MAX_PAGE),
        offset: int = Query(0, ge=0),
        user_id: str = Depends(current_user),
    ) -> FactPage:
        items, has_more = await api.list_facts(user_id, limit=limit, offset=offset)
        return FactPage(
            items=[
                FactOut(
                    id=i.id,
                    content=i.content,
                    kind=getattr(i.kind, "value", str(i.kind)),
                    source_character_id=getattr(i, "source_character_id", ""),
                    created_at=i.created_at,
                )
                for i in items
            ],
            has_more=has_more,
        )

    @router.delete("/memory/{memory_id}", status_code=204)
    async def delete_memory(memory_id: str, user_id: str = Depends(current_user)):
        # 别人的 id 与不存在的 id 返回同样的 404：不泄露「这条存在但不是你的」。
        if not await api.delete_fact(user_id, memory_id):
            raise HTTPException(status_code=404, detail="memory not found")

    @router.get("/events", response_model=list[EventOut])
    async def list_events(
        limit: int = Query(DEFAULT_PAGE, ge=1, le=MAX_PAGE),
        include_past: bool = False,
        user_id: str = Depends(current_user),
    ) -> list[EventOut]:
        events = await api.list_events(user_id, limit=limit, include_past=include_past)
        return [
            EventOut(
                id=e.id,
                title=e.title,
                kind=e.kind.value,
                at=e.at,
                status=e.status.value,
                confidence=e.confidence,
            )
            for e in events
        ]

    @router.post("/events", response_model=EventOut, status_code=201)
    async def add_event(body: EventIn, user_id: str = Depends(current_user)) -> EventOut:
        event = await api.add_event(user_id, title=body.title, at=body.at, kind=body.kind)
        return EventOut(
            id=event.id,
            title=event.title,
            kind=event.kind.value,
            at=event.at,
            status=event.status.value,
            confidence=event.confidence,
        )

    @router.post("/events/{event_id}/{status}", status_code=204)
    async def set_status(event_id: str, status: str, user_id: str = Depends(current_user)):
        try:
            changed = await api.set_status(user_id, event_id, status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not changed:
            raise HTTPException(status_code=404, detail="event not found")

    @router.delete("/events/{event_id}", status_code=204)
    async def delete_event(event_id: str, user_id: str = Depends(current_user)):
        if not await api.delete_event(user_id, event_id):
            raise HTTPException(status_code=404, detail="event not found")

    return router
