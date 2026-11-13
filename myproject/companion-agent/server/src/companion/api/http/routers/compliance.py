"""合规接口（前缀 /v1）。不用 __future__ 注解。

- ``GET /consent`` / ``PATCH /consent``：训练用途同意（默认关）、主动联系总开关、是否成年人。
- ``GET /export``：导出自己的全部数据（JSON 下载）。办法要求可复制。
- 连续使用提醒不在这里：它随回合的 SSE（``usage.reminder``）下发，客户端展示一次即可。
"""

from datetime import datetime
from typing import Any

from companion.compliance.service import export_user_data

PREFIX = "/v1"


def _consent_json(c) -> dict[str, Any]:
    return {"training_consent": c.training_consent, "proactive_enabled": c.proactive_enabled,
            "age_verified_adult": c.age_verified_adult, "qa_retention": c.qa_retention}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def build_router(service, current_user, *, sessions, messages, persona, timeline, reminders):
    from fastapi import APIRouter, Depends, Response
    from pydantic import BaseModel

    class ConsentIn(BaseModel):
        training_consent: bool | None = None
        proactive_enabled: bool | None = None
        age_verified_adult: bool | None = None
        qa_retention: bool | None = None

    router = APIRouter(prefix=PREFIX, tags=["compliance"])

    def uid(user_id: str) -> int:
        from fastapi import HTTPException

        if not user_id.isdigit():
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return int(user_id)

    @router.get("/consent")
    async def get_consent(user_id: str = Depends(current_user)) -> dict[str, Any]:
        return _consent_json(await service.consent(owner_id=uid(user_id)))

    @router.patch("/consent")
    async def patch_consent(body: ConsentIn, user_id: str = Depends(current_user)) -> dict[str, Any]:
        return _consent_json(await service.update(
            owner_id=uid(user_id), training_consent=body.training_consent,
            proactive_enabled=body.proactive_enabled, age_verified_adult=body.age_verified_adult,
            qa_retention=body.qa_retention))

    @router.get("/export")
    async def export(user_id: str = Depends(current_user)) -> Response:
        import json

        data = await export_user_data(owner_id=uid(user_id), sessions=sessions, messages=messages,
                                      persona=persona, timeline=timeline, reminders=reminders, consent=service)
        body = json.dumps(_jsonable(data), ensure_ascii=False, indent=2)
        return Response(content=body, media_type="application/json; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="companion-export.json"'})

    return router
