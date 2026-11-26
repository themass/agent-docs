"""Authenticated raw-body photo solving, independent of chat sessions.

两条通道共用同一请求体契约（原始图片字节 + query 参数）：
- POST /solve：全量 JSON（行为与老客户端完全一致）。
- POST /solve/stream：`Accept: text/event-stream` 的 SSE 通道——事件帧复用
  chat 线同一编码器（api/sse/encoder），事件序列见 service/photosolve_stream。
  错误语义同源：进入流之前的错误（鉴权、参数、图片）仍是普通 HTTP JSON；
  流开始之后（模型失败、限时）发 error 事件再正常关流——流已开始就没法改状态码了。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from companion.api.sse.encoder import KEEPALIVE_FRAME, encode_event
from companion.service.photosolve import PhotoSolveError, PhotoSolveService
from companion.service.uploads.policy import MAX_BYTES


def _detail(exc: PhotoSolveError) -> dict:
    return {"code": exc.code, "message": exc.message}


def build_router(service: PhotoSolveService, current_user) -> APIRouter:
    router = APIRouter(prefix="/v1/photosolve", tags=["photosolve"])

    async def read_image(request: Request, client_request_id: str | None,
                         subject: str) -> bytes:
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
        return bytes(data)

    @router.post("/solve")
    async def solve(
        request: Request,
        client_request_id: Annotated[str | None, Query()] = None,
        subject: Annotated[str, Query()] = "math",
        user_id: str = Depends(current_user),
    ) -> dict:
        data = await read_image(request, client_request_id, subject)
        try:
            return await service.solve(data, request_id=client_request_id)
        except PhotoSolveError as exc:
            raise HTTPException(exc.status, detail=_detail(exc)) from exc

    @router.post("/solve/stream")
    async def solve_stream(
        request: Request,
        client_request_id: Annotated[str | None, Query()] = None,
        subject: Annotated[str, Query()] = "math",
        user_id: str = Depends(current_user),
    ) -> StreamingResponse:
        data = await read_image(request, client_request_id, subject)
        # 图片校验也发生在开流之前：40003 这类错误用既有 HTTP JSON 语义，不发流。
        try:
            url = await service.prepare(data)
        except PhotoSolveError as exc:
            raise HTTPException(exc.status, detail=_detail(exc)) from exc

        async def frames():
            # event_id 用流内单调序号：这个流没有 Redis 重放，断线重连按客户端协议
            # 重发同一个 requestId（服务端幂等缓存会回放），Last-Event-ID 不参与。
            seq = 0
            async for name, payload in service.solve_stream(url, request_id=client_request_id):
                if name == "keepalive":
                    yield KEEPALIVE_FRAME
                    continue
                seq += 1
                yield encode_event(str(seq), name, payload)

        return StreamingResponse(frames(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return router
