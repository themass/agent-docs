from __future__ import annotations
from collections.abc import Awaitable, Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from agentkit.common.trace import bind_trace_context, clear_trace_context, new_trace_id

def create_app(*, title: str, version: str = "0.1.0") -> FastAPI:
    app = FastAPI(title=title, version=version)
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}
    return app

class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id") or request.headers.get("x-trace-id")
        trace_id = incoming or new_trace_id()
        bind_trace_context(trace_id=trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            clear_trace_context()
