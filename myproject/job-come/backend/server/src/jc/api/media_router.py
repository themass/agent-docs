"""Direct-upload sign route (ADR-011).

`POST /media/sign` hands the browser a one-key, write-only presigned PUT. The
business endpoint that later receives the `objectKey` performs the bind (see
`jc.services.media_service.MediaService.bind`) — there is no separate
`complete` call, by design.
"""

from __future__ import annotations

from agentkit.web.auth import Actor
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from jc.api.deps import get_actor, get_db
from jc.exceptions import (
    GoneError,
    ServiceUnavailableError,
    TooManyRequestsError,
)
from jc.schemas.media import MediaSignRequest, MediaSignResponse
from jc.services.media_service import MediaService

router = APIRouter(prefix="/media", tags=["media"])


@router.post(
    "/sign",
    response_model=MediaSignResponse,
    summary="申请直传上传凭证",
    description=(
        "按场景签发一次性预签名 PUT。返回的 upload.url 是 bearer secret：只用一次、"
        "不写日志、不进埋点。503 表示直传未启用（dev 本地盘），调用方回退 multipart。"
    ),
)
async def sign_media_upload(
    body: MediaSignRequest,
    actor: Actor = Depends(get_actor),
    db: AsyncSession = Depends(get_db),
) -> MediaSignResponse:
    result = await MediaService(db).sign(
        actor=actor,
        scene=body.scene,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )
    return MediaSignResponse.model_validate(result)


def register_media_exception_handlers(app) -> None:
    """Media-specific status codes; the rest ride the shared AppError handlers."""

    @app.exception_handler(GoneError)
    async def gone_handler(_request: Request, exc: GoneError) -> JSONResponse:
        return JSONResponse(status_code=410, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(TooManyRequestsError)
    async def rate_handler(_request: Request, exc: TooManyRequestsError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(ServiceUnavailableError)
    async def unavailable_handler(_request: Request, exc: ServiceUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"code": exc.code, "message": exc.message})
