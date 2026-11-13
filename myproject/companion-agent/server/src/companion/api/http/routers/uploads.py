"""上传接口（O §5）。前缀 /v1。原始字节上传，不依赖 multipart。不用 __future__ 注解。"""

from typing import Any

from companion.service.uploads.service import UploadService
from companion.service.uploads.policy import UploadRejected

PREFIX = "/v1"


def build_router(service: UploadService, current_user):
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

    @router.get("/uploads/{upload_id}")
    async def read_upload(upload_id: str, user_id: str = Depends(current_user)) -> dict[str, Any]:
        if not user_id.isdigit():
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        url = await service.read_url(owner_id=int(user_id), upload_id=upload_id)
        if url is None:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        return {"url": url, "expires_in": 300}

    return router
