"""Authenticated reads for objects stored on the local filesystem (dev fallback)."""

from __future__ import annotations

import asyncio
import mimetypes
from typing import Annotated

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends, Path
from fastapi.responses import Response

from jc.api.deps import get_profile_service, require_user
from jc.config import settings
from jc.exceptions import ForbiddenError, NotFoundError
from jc.services.profile_service import ProfileService
from jc.storage_backend import get_storage_backend
from jc.storage_keys import profile_id_and_kind_from_key

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get(
    "/objects/{storage_key:path}",
    summary="下载本地存储对象",
    description="当未配置 TOS 时，导出等产物通过此路由在同域下载（需登录且有权访问对应档案）。",
)
async def download_storage_object(
    storage_key: Annotated[str, Path(description="对象 storage_key")],
    actor: UserActor = Depends(require_user),
    profiles: ProfileService = Depends(get_profile_service),
) -> Response:
    if settings.storage_remote_enabled:
        raise NotFoundError("对象不存在或已过期。")

    parsed = profile_id_and_kind_from_key(storage_key)
    if parsed is None:
        raise ForbiddenError("无权访问该对象。")
    profile_id, _kind = parsed

    await profiles.get(profile_id, actor=actor)

    normalized = storage_key.strip("/")
    try:
        body = await asyncio.to_thread(get_storage_backend().get_object_bytes, normalized)
    except (FileNotFoundError, ValueError, OSError):
        raise NotFoundError("对象不存在或已过期。") from None

    media_type, _ = mimetypes.guess_type(normalized)
    filename = normalized.rsplit("/", 1)[-1]
    return Response(
        content=body,
        media_type=media_type or "application/octet-stream",
        headers={
            "Cache-Control": "private, max-age=60",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
