"""上传接口（O §5）。前缀 /v1。

两条通道并存：
- ``POST /v1/uploads``：中转（原始字节过服务端）。保留作直传的降级通道。
- ``POST /v1/uploads/sign``：直传的签发（ADR-011 同款）：返回单 key、只写、10 分钟的
  presigned PUT URL，字节直进 TOS；发消息时用 upload_id 绑定校验（chat 路由负责）。
"""

from typing import Any

from companion.service.uploads.service import UploadService
from companion.service.uploads.policy import UploadRejected
from companion.service.uploads.direct import DirectRejected

PREFIX = "/v1"


def build_router(service: UploadService, current_user, direct=None):
    from fastapi import APIRouter, Depends, HTTPException, Request

    router = APIRouter(prefix=PREFIX, tags=["uploads"])

    @router.post("/uploads", status_code=201)
    async def upload(request: Request, user_id: str = Depends(current_user)) -> dict[str, Any]:
        if not user_id.isdigit():
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        data = await request.body()
        try:
            record = await service.accept(owner_id=int(user_id), data=data)
        except UploadRejected as exc:
            raise HTTPException(status_code=422, detail={"code": "upload_rejected", "reason": str(exc)}) from exc
        return {"upload_id": record.id, "mime": record.mime, "width": record.width, "height": record.height,
                "size": record.size}

    if direct is not None:
        @router.post("/uploads/sign")
        async def sign(request: Request, user_id: str = Depends(current_user)) -> dict[str, Any]:
            if not user_id.isdigit():
                raise HTTPException(status_code=404, detail={"code": "not_found"})
            try:
                body = await request.json()
                return await direct.sign(
                    owner_id=int(user_id),
                    scene=str(body.get("scene", "")),
                    content_type=str(body.get("content_type", "")),
                    size_bytes=int(body.get("size_bytes", 0)),
                )
            except DirectRejected as exc:
                status = {"SIZE_NOT_ALLOWED": 413, "KEY_NOT_PUT": 412}.get(exc.code, 400)
                raise HTTPException(status_code=status, detail={"code": exc.code}) from exc
            except (ValueError, TypeError) as exc:  # 请求体不是合法 JSON/数字
                raise HTTPException(status_code=400, detail={"code": "bad_request"}) from exc

    @router.get("/uploads/{upload_id}")
    async def read_upload(upload_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
        if not user_id.isdigit():
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        url = await service.read_url(owner_id=int(user_id), upload_id=upload_id)
        if url is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"url": url, "expires_in": 300}

    return router
