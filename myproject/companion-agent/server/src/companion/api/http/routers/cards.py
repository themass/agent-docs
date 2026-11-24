"""角色卡接口（P6）。前缀 /v1/cards。不用 __future__ 注解（deps 的约定）。

一个 (用户, 角色) 一张卡。读 = active 版本合并后的字段（含渲染行，客户端不用自己拼）；
写 = 追加一个变更集版本并激活；回退 = activate 指回旧版本号。历史永远可列。

隔离口径与记忆接口一致：别人的卡与不存在的卡都读成「空」或 404，不可区分。
"""

from companion.service.card.model import CardChangeInvalid, render_card_lines
from companion.service.card.store import CardNotFound

PREFIX = "/v1"


def _uid(user_id: str) -> int:
    """卡的 owner_id 是整数；登录态已保证是正整数，非数字按不存在处理（同 memory_v1）。"""
    from fastapi import HTTPException

    if not user_id.isdigit():
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return int(user_id)


def build_router(service, current_user):
    from fastapi import APIRouter, Body, Depends, HTTPException, Path
    from pydantic import BaseModel, Field

    class VersionIn(BaseModel):
        changes: dict = Field(min_length=1)

    class ActivateIn(BaseModel):
        version: int = Field(ge=1)

    router = APIRouter(prefix=f"{PREFIX}/cards", tags=["cards"])

    def role_p():
        return Path(min_length=1, max_length=128)

    @router.get("/{role_id}")
    async def get_card(role_id: str = role_p(), user_id: str = Depends(current_user)) -> dict:
        eff = await service.effective(owner_id=_uid(user_id), role_id=role_id)
        if eff is None:
            # 没有卡不是错误：active 语义下读成空字段，客户端按默认角色资产走
            return {"role_id": role_id, "version": 0, "fields": {}, "lines": []}
        return {"role_id": eff.role_id, "version": eff.version, "fields": eff.fields,
                "lines": render_card_lines(eff.fields)}

    @router.get("/{role_id}/versions")
    async def list_versions(role_id: str = role_p(), user_id: str = Depends(current_user)) -> dict:
        versions = await service.list_versions(owner_id=_uid(user_id), role_id=role_id)
        return {"versions": [
            {"version": v.version, "changes": v.changes, "created_at": v.created_at.isoformat()}
            for v in versions]}

    @router.post("/{role_id}/versions", status_code=201)
    async def append_version(role_id: str = role_p(), body: VersionIn = Body(...),
                             user_id: str = Depends(current_user)) -> dict:
        try:
            record = await service.append_version(owner_id=_uid(user_id), role_id=role_id,
                                                  changes=body.changes)
        except CardChangeInvalid as exc:
            raise HTTPException(status_code=422, detail={"code": "validation", "message": str(exc)})
        except CardNotFound:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"version": record.version, "changes": record.changes,
                "created_at": record.created_at.isoformat()}

    @router.post("/{role_id}/activate")
    async def activate(role_id: str = role_p(), body: ActivateIn = Body(...),
                       user_id: str = Depends(current_user)) -> dict:
        try:
            card = await service.set_active(owner_id=_uid(user_id), role_id=role_id,
                                            version=body.version)
        except CardNotFound:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"role_id": role_id, "active_version": card.active_version}

    return router
