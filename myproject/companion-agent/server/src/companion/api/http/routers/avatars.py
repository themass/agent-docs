"""形象接口（前缀 /v1）。不用 __future__ 注解。

- 客户端：``GET /avatars?role_id=&app_version=`` —— 该角色可用的、已上线的最新形象，带短期下载地址与校验值。
  客户端比较本地版本，需要时下载 zip、核对 sha256、解压后按 manifest 渲染；服务端下线的形象下次同步时不再出现。
- 运营：``/admin/avatars``，用 ``X-Admin-Token`` 鉴权（配置里没有设置管理令牌时一律拒绝，不留默认口令）。
  上传 → 草稿 → 上线 / 下线。上线新版本会让同一个形象的旧在线版本自动下线。
"""

import hmac
from typing import Any

from companion.service.avatar.catalog import AvatarCatalog, ReleaseNotFound, ReleaseStateError
from companion.service.avatar.package import MAX_PACKAGE_BYTES, InvalidPackage

PREFIX = "/v1"


def _release_json(r) -> dict[str, Any]:
    return {"id": r.id, "avatar_key": r.avatar_key, "version": r.version, "name": r.name,
            "role_id": r.role_id or None, "status": r.status, "size_bytes": r.size_bytes, "sha256": r.sha256,
            "min_app_version": r.min_app_version,
            "published_at": r.published_at.isoformat() if r.published_at else None}


def build_router(catalog: AvatarCatalog, current_user, *, admin_token: str):
    from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile

    router = APIRouter(prefix=PREFIX, tags=["avatars"])

    def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
        # 未配置令牌 = 管理接口关闭（fail-closed）；比较用常量时间。
        if not admin_token or not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
            raise HTTPException(status_code=403, detail={"code": "forbidden"})

    @router.get("/avatars")
    async def list_for_client(role_id: str = Query(default="", max_length=128),
                              app_version: int = Query(default=0, ge=0),
                              user_id: str = Depends(current_user)) -> dict[str, Any]:
        return {"items": await catalog.for_client(role_id=role_id, app_version=app_version)}

    @router.get("/admin/avatars", dependencies=[Depends(require_admin)])
    async def admin_list(avatar_key: str | None = Query(default=None, max_length=64)) -> dict[str, Any]:
        return {"items": [_release_json(r) for r in await catalog.list_releases(avatar_key=avatar_key)]}

    @router.post("/admin/avatars", status_code=201, dependencies=[Depends(require_admin)])
    async def admin_upload(avatar_key: str = Form(min_length=1, max_length=64),
                           role_id: str = Form(default="", max_length=128),
                           min_app_version: int = Form(default=0, ge=0),
                           package: UploadFile = File(...)) -> dict[str, Any]:
        data = await package.read(MAX_PACKAGE_BYTES + 1)   # 多读一个字节：超限由校验报错，不把大文件整个读进内存
        try:
            release = await catalog.upload(avatar_key=avatar_key, role_id=role_id, data=data,
                                           min_app_version=min_app_version)
        except InvalidPackage as exc:
            raise HTTPException(status_code=422, detail={"code": "validation", "reason": str(exc)})
        return _release_json(release)

    @router.post("/admin/avatars/{release_id}/publish", dependencies=[Depends(require_admin)])
    async def admin_publish(release_id: int) -> dict[str, Any]:
        try:
            return _release_json(await catalog.publish(release_id))
        except ReleaseNotFound:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        except ReleaseStateError as exc:
            raise HTTPException(status_code=409, detail={"code": "conflict", "reason": str(exc)})

    @router.post("/admin/avatars/{release_id}/offline", dependencies=[Depends(require_admin)])
    async def admin_offline(release_id: int) -> dict[str, Any]:
        try:
            return _release_json(await catalog.offline(release_id))
        except ReleaseNotFound:
            raise HTTPException(status_code=404, detail={"code": "not_found"})

    return router
