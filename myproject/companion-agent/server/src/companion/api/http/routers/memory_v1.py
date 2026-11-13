"""记忆接口 v1（D §7.1、§10.5）。前缀 /v1/memory。不用 __future__ 注解。

复用 MemoryApi 的用户隔离、分页夹取与删除语义（已在旧路由上测过）。
PATCH 事实记忆采用「删除旧条目 + 写入新条目」：后端没有原地更新接口，因此 id 会变化，
返回值里给出新 id。

记忆按角色隔离：事实接口都带可选的 ``role_id``，给了就只读写该角色的记忆空间
（domain/memory/subject.py）；不给是用户级空间（手动添加、不属于任何角色的记忆）。
事件按 ``source_character_id`` 过滤。
"""

import uuid
from typing import Any

from companion.app.chat.ids import new_ulid
from companion.memory.subject import role_subject
from companion.domain.timeline.models import EventKind, EventOrigin, EventStatus, TimelineEvent
from companion.memory.port import MemoryItem, MemoryKind

PREFIX = "/v1"


def _uid(user_id: str) -> int:
    """画像表的 owner_id 是整数；登录态已保证是正整数，非数字按不存在处理。"""
    from fastapi import HTTPException

    if not user_id.isdigit():
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return int(user_id)


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
        "recurrence": event.recurrence.value,
        "all_day": event.all_day,
        "reminder_id": event.reminder_id,
        "session_id": event.session_id,
    }


def build_router(*, memory, timeline, current_user, persona=None):
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

    def role_q():
        return Query(default=None, min_length=1, max_length=128)

    @router.get("/facts")
    async def list_facts(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0, le=1000),
                         role_id: str | None = role_q(), include_history: bool = False,
                         user_id: str = Depends(current_user)) -> dict[str, Any]:
        """默认只列当前有效的；``include_history`` 带上被取代的（看「改过什么」）。"""
        rows = await memory.list_for_user(role_subject(user_id, role_id), limit=limit + 1, offset=offset,
                                          include_history=include_history)
        return {"items": [_fact_json(i) for i in rows[:limit]], "has_more": len(rows) > limit,
                "limit": limit, "offset": offset}

    @router.post("/facts", status_code=201)
    async def add_fact(body: FactIn, role_id: str | None = role_q(),
                       user_id: str = Depends(current_user)) -> dict[str, Any]:
        kind = MemoryKind.EVENT if body.kind.upper() == "EVENT" else MemoryKind.FACT
        item = MemoryItem(id=uuid.uuid4().hex, content=body.content, kind=kind, source_character_id=role_id or "")
        await memory.add(role_subject(user_id, role_id), [item])
        return _fact_json(item)

    @router.patch("/facts/{fact_id}")
    async def edit_fact(fact_id: str, body: FactPatch, role_id: str | None = role_q(),
                        user_id: str = Depends(current_user)) -> dict[str, Any]:
        subject = role_subject(user_id, role_id)
        # 改写 = 取代，不是删除再新增：旧条目保留可回溯，新条目从旧条目接上来源，画像不会因此失去依据
        item = MemoryItem(id=uuid.uuid4().hex, content=body.content, kind=MemoryKind.FACT,
                          source_character_id=role_id or "")
        superseded = await memory.supersede(subject, fact_id, item)
        if superseded is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return _fact_json(superseded)

    @router.delete("/facts/{fact_id}", status_code=204)
    async def delete_fact(fact_id: str, role_id: str | None = role_q(),
                          user_id: str = Depends(current_user)) -> Response:
        if not await memory.delete_one(role_subject(user_id, role_id), fact_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        if persona is not None:
            # 联动：只靠这条事实归纳出来的画像条目一并删除，用户说「忘掉」就真的忘掉
            await persona.drop_for_facts(owner_id=_uid(user_id), fact_ids=[fact_id])
        return Response(status_code=204)

    @router.get("/events")
    async def list_events(limit: int = Query(default=20, ge=1, le=100), include_past: bool = False,
                          role_id: str | None = role_q(),
                          user_id: str = Depends(current_user)) -> dict[str, Any]:
        events = await timeline.list_for_owner(owner_id=user_id, role_id=role_id, include_past=include_past,
                                               limit=limit)
        return {"items": [_event_json(e) for e in events]}

    @router.post("/events", status_code=201)
    async def add_event(body: EventIn, role_id: str | None = role_q(),
                        user_id: str = Depends(current_user)) -> dict[str, Any]:
        event = TimelineEvent(
            id="", user_id=user_id,
            kind=EventKind(body.kind) if body.kind in EventKind._value2member_map_ else EventKind.OTHER,
            title=body.title, at=body.at, source_character_id=role_id or "",
            origin=EventOrigin.MANUAL, confidence=1.0)  # 用户亲口说的，可信度最高
        return _event_json(await timeline.upsert(event))

    @router.patch("/events/{event_id}")
    async def set_event_status(event_id: str, body: EventStatusIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
        if body.status not in {s.value for s in EventStatus}:
            raise HTTPException(status_code=422, detail={"code": "validation", "reason": "unknown status"})
        if not await timeline.set_status(owner_id=user_id, public_id=event_id, status=EventStatus(body.status)):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"id": event_id, "status": body.status}

    @router.delete("/events/{event_id}", status_code=204)
    async def delete_event(event_id: str, user_id: str = Depends(current_user)) -> Response:
        if not await timeline.delete(owner_id=user_id, public_id=event_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    def _entry_json(e) -> dict[str, Any]:
        return {"id": e.id, "topic": e.topic, "memo": e.memo, "section": e.section,
                "is_inference": e.is_inference, "confidence": e.confidence,
                "source_fact_ids": list(e.source_fact_ids), "suppressed": e.suppressed,
                "superseded_by": e.superseded_by,
                "mentioned_at": e.mentioned_at.isoformat() if e.mentioned_at else None}

    @router.get("/profile")
    async def profile(role_id: str | None = role_q(), include_history: bool = False,
                      user_id: str = Depends(current_user)) -> dict[str, Any]:
        """这个角色对你的了解：当前有效的条目；``include_history`` 时带上被取代和被压住的（「为什么记得」）。
        没有画像存储（未配置）或还没有生成就明确返回空，不编造。"""
        if persona is None or not role_id:
            return {"items": [], "markdown": None, "version": None}
        entries = await persona.list_entries(owner_id=_uid(user_id), role_id=role_id, include_history=include_history)
        return {"items": [_entry_json(e) for e in entries], "markdown": None, "version": None}

    @router.post("/profile/{entry_id}/suppress", status_code=204)
    async def suppress_entry(entry_id: int, user_id: str = Depends(current_user)) -> Response:
        """「别再提」：这条不再注入提示词，同一话题也不会被重新生成。"""
        if persona is None or not await persona.suppress(owner_id=_uid(user_id), entry_id=entry_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    @router.delete("/profile/{entry_id}", status_code=204)
    async def delete_entry(entry_id: int, user_id: str = Depends(current_user)) -> Response:
        if persona is None or not await persona.delete(owner_id=_uid(user_id), entry_id=entry_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    return router
