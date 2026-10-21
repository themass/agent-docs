"""JC API entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from agentkit.common.logging import configure_logging
from agentkit.web import TraceMiddleware
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from jc.api.auth_router import register_exception_handlers
from jc.api.openapi import OPENAPI_TAGS, attach_openapi
from jc.api.profile_router import register_profile_exception_handlers
from jc.api.router import api_router
from jc.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(json_logs=settings.jc_log_json, level=settings.jc_log_level)
    from jc.observability.logging_setup import configure_application_logging

    configure_application_logging(json_logs=settings.jc_log_json, level=settings.jc_log_level)
    from jc.llm.bootstrap import configure_litellm
    from jc.observability.langfuse_setup import setup_langfuse_callbacks

    configure_litellm()
    setup_langfuse_callbacks()
    from jc.tasks import run_profile_parse_dispatcher

    # The source table is the durable queue. Every API instance may poll it;
    # database lease claims ensure one instance owns each parse attempt.
    dispatcher = asyncio.create_task(run_profile_parse_dispatcher())
    try:
        yield
    finally:
        dispatcher.cancel()
        try:
            await dispatcher
        except asyncio.CancelledError:
            pass


_api_prefix = settings.jc_api_prefix.rstrip("/")
_docs_enabled = settings.jc_docs_enabled

app = FastAPI(
    title="JC API",
    version="0.1.0",
    lifespan=lifespan,
    description="JC 简历优化与面试辅导 API",
    openapi_tags=OPENAPI_TAGS,
    docs_url=f"{_api_prefix}/docs" if _docs_enabled else None,
    redoc_url=f"{_api_prefix}/redoc" if _docs_enabled else None,
    openapi_url=f"{_api_prefix}/openapi.json" if _docs_enabled else None,
)
attach_openapi(app)
app.add_middleware(TraceMiddleware)
register_exception_handlers(app)
register_profile_exception_handlers(app)


@app.exception_handler(PermissionError)
async def permission_error_handler(_request, exc):
    return JSONResponse(status_code=403, content={"detail": str(exc), "code": "forbidden"})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request, exc: SQLAlchemyError):
    # Do not expose driver details or reset the frontend proxy connection on transient DB outages.
    logger.error("Database request failed", exc_info=exc)
    return JSONResponse(
        status_code=503,
        content={
            "code": "database_unavailable",
            "message": "服务暂时繁忙，请稍后重试。",
        },
        headers={"Retry-After": "5"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/llm")
async def health_llm() -> dict[str, object]:
    """Quick check: is LLM enabled and are API keys present?"""
    vision_key = settings.jc_llm_vision_api_key or settings.jc_llm_api_key
    return {
        "llm_enabled": settings.jc_llm_enabled,
        "llm_api_key_set": bool(settings.jc_llm_api_key),
        "llm_vision_api_key_set": bool(vision_key),
        "routing_path": settings.jc_llm_routing_path,
    }


if _docs_enabled:

    @app.get("/docs", include_in_schema=False)
    async def redirect_docs() -> RedirectResponse:
        return RedirectResponse(url=f"{_api_prefix}/docs")

    @app.get("/redoc", include_in_schema=False)
    async def redirect_redoc() -> RedirectResponse:
        return RedirectResponse(url=f"{_api_prefix}/redoc")


app.include_router(api_router, prefix=settings.jc_api_prefix)
