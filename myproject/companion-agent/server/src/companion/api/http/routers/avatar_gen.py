"""二次元头像生成的两个动作（``POST /v1/avatars/generate`` / ``POST /v1/avatars/apply``）。

对端是 Android 的 ``AvatarGenRemote``；契约见其 ``docs/design/2026-11-24-anime-avatar-mvp.md`` §3。

与 ``routers/avatars.py`` 是**两个特性**：那边是角色形象包目录（GET /v1/avatars +
/admin 运营线），这里是「我」的头像生成。共享 /v1/avatars 前缀但语义分开——所以
router 单独一个文件、tag 用 avatar-gen，改任何一边都不会顺手碰另一边。

错误形状沿用 /v1 全线：非 2xx + ``{"detail": {"code": ...}}``。端侧 ``mapStatus``
只认 status 与 code（422→BAD_IMAGE、429→QUOTA），message 原文不外泄；分类逻辑
在 service 层（那里才看得见归属与配额），路由只做 HTTP 翻译。
"""

from typing import Any

from companion.service.avatar_gen.port import AvatarGenError
from companion.service.avatar_gen.service import AvatarGenService


def build_router(service: AvatarGenService, current_user):
    from fastapi import APIRouter, Depends, HTTPException, Request

    router = APIRouter(prefix="/v1/avatars", tags=["avatar-gen"])

    def require_owner(user_id: str) -> int:
        # 与 uploads 路由同判据：owner id 是 Java 的 long，非数字用户没有头像语义。
        if not user_id.isdigit():
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return int(user_id)

    async def json_body(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError) as exc:  # 不是合法 JSON：客户端 bug
            raise HTTPException(status_code=400, detail={"code": "bad_request"}) from exc
        return body if isinstance(body, dict) else {}

    @router.post("/generate")
    async def generate(request: Request, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner_id = require_owner(user_id)
        body = await json_body(request)
        try:
            return await service.generate(
                owner_id=owner_id,
                source_upload_id=str(body.get("source_upload_id", "")),
                style=str(body.get("style", "")),
            )
        except AvatarGenError as exc:
            raise HTTPException(status_code=exc.status, detail={"code": exc.code}) from exc

    @router.post("/apply")
    async def apply(request: Request, user_id: str = Depends(current_user)) -> dict[str, Any]:
        owner_id = require_owner(user_id)
        body = await json_body(request)
        try:
            return await service.apply(owner_id=owner_id,
                                       avatar_upload_id=str(body.get("avatar_upload_id", "")))
        except AvatarGenError as exc:
            raise HTTPException(status_code=exc.status, detail={"code": exc.code}) from exc

    return router
