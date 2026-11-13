"""工具确认接口（T §2.4、D §7.1）。前缀 /v1。不用 __future__ 注解。"""

from typing import Any

from companion.api.http.routers.chat import _owner_id
from companion.tools.confirmation import ConfirmationService

PREFIX = "/v1"


def build_router(service: ConfirmationService, current_user):
    from fastapi import APIRouter, Depends, HTTPException
    from pydantic import BaseModel

    class ConfirmBody(BaseModel):
        accepted: bool

    router = APIRouter(prefix=PREFIX, tags=["actions"])

    @router.get("/actions/pending")
    async def pending(user_id: str = Depends(current_user)) -> dict[str, Any]:
        rows = await service.pending(owner_id=_owner_id(user_id))
        return {"items": [
            {"confirmation_id": r.id, "title": r.title, "summary": r.summary,
             "expires_at": r.expires_at.isoformat()}
            for r in rows
        ]}

    @router.post("/actions/{confirmation_id}/confirm")
    async def confirm(confirmation_id: str, body: ConfirmBody,
                      user_id: str = Depends(current_user)) -> dict[str, Any]:
        # 不属于本人、不存在、或已处理：统一 404，不泄露存在性（T §2.4）。
        result = await service.decide(owner_id=_owner_id(user_id), confirmation_id=confirmation_id,
                                      accept=body.accepted)
        if result is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"status": result.status, "message_id": result.message_id}

    return router
