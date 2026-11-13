"""角色接口（D §5.3）。前缀 /v1。不用 __future__ 注解（FastAPI 运行时注解）。"""

from typing import Any

from companion.roles.service import RoleForbidden, RoleService
from companion.roles.catalog import negotiate_locale

PREFIX = "/v1"


def _owner_id(user_id: str) -> int:
    from fastapi import HTTPException

    if not user_id.isdigit():
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return int(user_id)


def build_router(service: RoleService, current_user):
    from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
    from pydantic import BaseModel, Field

    class CreateRole(BaseModel):
        name: str = Field(min_length=1, max_length=40)
        description: str = Field(default="", max_length=280)
        prompt: str = Field(min_length=1, max_length=4000)
        locale: str | None = Field(default=None, max_length=16)

    class UpdateRole(BaseModel):
        name: str | None = Field(default=None, min_length=1, max_length=40)
        description: str | None = Field(default=None, max_length=280)
        prompt: str | None = Field(default=None, min_length=1, max_length=4000)

    router = APIRouter(prefix=PREFIX, tags=["roles"])

    def locale_for(explicit: str | None, accept_language: str | None) -> str:
        return negotiate_locale(explicit, accept_language)

    @router.get("/divisions")
    async def divisions(locale: str | None = Query(default=None),
                        accept_language: str | None = Header(default=None, alias="Accept-Language")) -> dict[str, Any]:
        resolved = locale_for(locale, accept_language)
        return {"items": await service.divisions(locale=resolved)}

    @router.get("/roles")
    async def list_roles(
        request: Request,
        division: str | None = None,
        q: str | None = Query(default=None, max_length=64),
        featured: bool = False,
        mine: bool = False,
        locale: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1000),
        user_id: str = Depends(current_user),
        accept_language: str | None = Header(default=None, alias="Accept-Language"),
    ) -> dict[str, Any]:
        return await service.list_roles(
            owner_id=_owner_id(user_id), division=division, q=q, featured=featured, mine=mine,
            locale=locale_for(locale, accept_language), limit=limit, offset=offset)

    @router.get("/roles/{role_id}")
    async def get_role(role_id: str, locale: str | None = Query(default=None),
                       user_id: str = Depends(current_user),
                       accept_language: str | None = Header(default=None, alias="Accept-Language")) -> dict[str, Any]:
        found = await service.get(owner_id=_owner_id(user_id), role_id=role_id,
                                  locale=locale_for(locale, accept_language))
        if found is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return found

    @router.post("/roles", status_code=201)
    async def create_role(body: CreateRole, user_id: str = Depends(current_user),
                          accept_language: str | None = Header(default=None, alias="Accept-Language")) -> dict[str, Any]:
        resolved = locale_for(body.locale, accept_language)
        try:
            return await service.create(owner_id=_owner_id(user_id), name=body.name,
                                        description=body.description, prompt=body.prompt, locale=resolved)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "validation", "reason": str(exc)}) from exc

    @router.put("/roles/{role_id}")
    async def update_role(role_id: str, body: UpdateRole, user_id: str = Depends(current_user),
                          accept_language: str | None = Header(default=None, alias="Accept-Language")) -> dict[str, Any]:
        try:
            found = await service.update(owner_id=_owner_id(user_id), role_id=role_id,
                                         locale=locale_for(None, accept_language), name=body.name,
                                         description=body.description, prompt=body.prompt)
        except RoleForbidden as exc:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "reason": str(exc)}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"code": "validation", "reason": str(exc)}) from exc
        if found is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return found

    @router.delete("/roles/{role_id}", status_code=204)
    async def delete_role(role_id: str, user_id: str = Depends(current_user)) -> Response:
        try:
            deleted = await service.delete(owner_id=_owner_id(user_id), role_id=role_id)
        except RoleForbidden as exc:
            raise HTTPException(status_code=403, detail={"code": "forbidden", "reason": str(exc)}) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return Response(status_code=204)

    return router
