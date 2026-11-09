"""记忆接口 v1（D §7.1、§10.5）。前缀 /api/agent/v1/memory。不用 __future__ 注解。

复用 MemoryApi 的用户隔离、分页夹取与删除语义（已在旧路由上测过）。
PATCH 事实记忆采用「删除旧条目 + 写入新条目」：后端没有原地更新接口，因此 id 会变化，
返回值里给出新 id。
"""

import uuid
from typing import Any

from companion.app.chat.ids import new_ulid
from companion.domain.timeline.models import EventKind, EventStatus, TimelineEvent
from companion.ports.memory import MemoryItem, MemoryKind

PREFIX = "/api/agent/v1"


def _fact_json(item) -> dict[str, Any]:
    kind = getattr(item, "kind", MemoryKind.FACT)
    return {
        "id": item.id,
        "content": item.content,
        "kind": getattr(kind, "value", str(kind)),
        "source_character_id": getattr(item, "source_character_id", ""),
        "created_at": item.created_at.isoformat() if getattr(item, "created_at", None) else None,
    }


def _event_json(event: TimelineEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "title": event.title,
        "at": event.at.isoformat(),
        "kind": event.kind.value,
        "status": event.status.value,
        "source_character_id": event.source_character_id,
        "confidence": event.confidence,
    }


def build_router(*, memory, timeline, current_user):
    from fastapi import APIRouter, Depends, HTTPException, Query, Response
    from pydantic import AwareDatetime, BaseModel, Field

    class FactIn(BaseModel):
        content: str = Field(min_length=2, max_length=300)
        kind: str = Field(default="FACT", max_length=16)

    class FactPatch(BaseModel):
        content: str = Field(min_length=2, max_length=300)

    class EventIn(BaseModel):
        title: str = Field(min_length=1, max_length=60)
        at: AwareDatetime
        kind: str = "other"

    class EventStatusIn(BaseModel):
        status: str

    router = APIRouter(prefix=f"{PREFIX}/memory", tags=["memory"])

    @router.get("/facts")
    async def list_facts(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0, le=1000),
                         user_id: str = Depends(current_user)) -> dict[str, Any]:
        rows = await memory.list_for_user(user_id, limit=limit + 1, offset=offset)
        return {"items": [_fact_json(i) for i in rows[:limit]], "has_more": len(rows) > limit,
                "limit": limit, "offset": offset}

    @router.post("/facts", status_code=201)
    async def add_fact(body: FactIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
        kind = MemoryKind.EVENT if body.kind.upper() == "EVENT" else MemoryKind.FACT
        item = MemoryItem(id=uuid.uuid4().hex, content=body.content, kind=kind, source_character_id="")
        await memory.add(user_id, [item])
        return _fact_json(item)

    @router.patch("/facts/{fact_id}")
    async def edit_fact(fact_id: str, body: FactPatch, user_id: str = Depends(current_user)) -> dict[str, Any]:
        if not await memory.delete_one(user_id, fact_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        item = MemoryItem(id=uuid.uuid4().hex, content=body.content, kind=MemoryKind.FACT, source_character_id="")
        await memory.add(user_id, [item])
        return _fact_json(item)

    @router.delete("/facts/{fact_id}", status_code=204)
    async def delete_fact(fact_id: str, user_id: str = Depends(current_user)) -> Response:
        if not await memory.delete_one(user_id, fact_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    @router.get("/events")
    async def list_events(limit: int = Query(default=20, ge=1, le=100), include_past: bool = False,
                          user_id: str = Depends(current_user)) -> dict[str, Any]:
        events = await timeline.list_for_user(user_id, limit=limit, include_past=include_past)
        return {"items": [_event_json(e) for e in events]}

    @router.post("/events", status_code=201)
    async def add_event(body: EventIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
        event = TimelineEvent(
            id=new_ulid(), user_id=user_id,
            kind=EventKind(body.kind) if body.kind in EventKind._value2member_map_ else EventKind.OTHER,
            title=body.title, at=body.at, confidence=1.0)  # 用户亲口说的，可信度最高
        await timeline.add(event)
        return _event_json(event)

    @router.patch("/events/{event_id}")
    async def set_event_status(event_id: str, body: EventStatusIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
        if body.status not in {s.value for s in EventStatus}:
            raise HTTPException(status_code=422, detail={"code": "validation", "reason": "unknown status"})
        setter = getattr(timeline, "set_status", None)
        if setter is None:
            # 时间线端口还没有状态更新方法（T9 之后补）；明确返回未实现，而不是假装成功。
            raise HTTPException(status_code=501, detail={"code": "not_implemented"})
        if not await setter(user_id, event_id, EventStatus(body.status)):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"id": event_id, "status": body.status}

    @router.delete("/events/{event_id}", status_code=204)
    async def delete_event(event_id: str, user_id: str = Depends(current_user)) -> Response:
        if not await timeline.delete_one(user_id, event_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    @router.get("/profile")
    async def profile(user_id: str = Depends(current_user)) -> dict[str, Any]:
        # L3 画像由 P4 的汇总任务生成（D §10.6）；现在没有就明确返回空，而不是编造。
        return {"markdown": None, "version": None}

    return router
