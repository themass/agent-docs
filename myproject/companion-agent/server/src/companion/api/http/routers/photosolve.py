"""Authenticated raw-body photo solving, independent of chat sessions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from companion.service.photosolve import PhotoSolveError, PhotoSolveService
from companion.service.uploads.policy import MAX_BYTES


def build_router(service: PhotoSolveService, current_user) -> APIRouter:
    router = APIRouter(prefix="/v1/photosolve", tags=["photosolve"])

    @router.post("/solve")
    async def solve(
        request: Request,
        client_request_id: Annotated[str | None, Query()] = None,
        subject: Annotated[str, Query()] = "math",
        user_id: str = Depends(current_user),
    ) -> dict:
        if (not client_request_id or not client_request_id.strip()
                or len(client_request_id) > 128 or subject != "math"):
            raise HTTPException(400, detail={"code": 40003, "message": "请求参数无效"})
        # Content-Length is only an early rejection. Count actual streamed bytes too.
        length = request.headers.get("content-length")
        if length is not None:
            try:
                declared = int(length)
            except ValueError:
                declared = -1
            if declared < 0:
                raise HTTPException(400, detail={"code": 40003, "message": "请求长度无效"})
            if declared > MAX_BYTES:
                raise HTTPException(413, detail={"code": 40003, "message": "图片不能超过 8 MiB"})
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise HTTPException(413, detail={"code": 40003, "message": "图片不能超过 8 MiB"})
            data.extend(chunk)
        try:
            return await service.solve(bytes(data), request_id=client_request_id)
        except PhotoSolveError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message}) from exc

    return router
