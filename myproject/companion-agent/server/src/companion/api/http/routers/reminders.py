"""定时提醒接口（前缀 /v1）。创建只经由工具 + 确认流程；这里只提供查看与取消。不用 __future__ 注解。"""

from typing import Any

from companion.api.http.routers.chat import _owner_id
from companion.app.proactive.reminders import ReminderService
from companion.domain.reminders import local_time_text

PREFIX = "/v1"


def _json(r) -> dict[str, Any]:
    return {"reminder_id": r.id, "session_id": r.session_id, "role_id": r.role_id, "content": r.content,
            "due_at": r.due_at.isoformat() + "Z", "due_local": local_time_text(r.due_at, r.timezone),
            "timezone": r.timezone, "status": r.status}


def build_router(service: ReminderService, current_user):
    from fastapi import APIRouter, Depends, HTTPException, Response

    router = APIRouter(prefix=PREFIX, tags=["reminders"])

    @router.get("/reminders")
    async def list_reminders(include_done: bool = False, user_id: str = Depends(current_user)) -> dict[str, Any]:
        rows = await service.list(owner_id=_owner_id(user_id), include_done=include_done)
        return {"items": [_json(r) for r in rows]}

    @router.delete("/reminders/{reminder_id}", status_code=204)
    async def cancel(reminder_id: int, user_id: str = Depends(current_user)) -> Response:
        # 不属于本人、不存在、或已发送 / 已取消：统一 404，不泄露存在性。
        if not await service.cancel(owner_id=_owner_id(user_id), reminder_id=reminder_id):
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    return router
