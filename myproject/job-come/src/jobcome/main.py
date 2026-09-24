"""JobCome API entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from agentkit.common.logging import configure_logging
from agentkit.web import TraceMiddleware

from jobcome.api.openapi import OPENAPI_TAGS, attach_openapi
from jobcome.api.router import api_router
from jobcome.api.auth_router import register_exception_handlers
from jobcome.api.profile_router import register_profile_exception_handlers
from jobcome.config import settings


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(json_logs=settings.job_come_log_json, level=settings.job_come_log_level)
    from jobcome.llm.bootstrap import configure_litellm
    from jobcome.observability.langfuse_setup import setup_langfuse_callbacks

    configure_litellm()
    setup_langfuse_callbacks()
    yield


_api_prefix = settings.job_come_api_prefix.rstrip("/")
_docs_enabled = settings.job_come_docs_enabled

app = FastAPI(
    title="JobCome API",
    version="0.1.0",
    lifespan=lifespan,
    description="JobCome 简历优化与面试辅导 API",
    openapi_tags=OPENAPI_TAGS,
    docs_url=f"{_api_prefix}/docs" if _docs_enabled else None,
    redoc_url=f"{_api_prefix}/redoc" if _docs_enabled else None,
    openapi_url=f"{_api_prefix}/openapi.json" if _docs_enabled else None,
)
attach_openapi(app)
app.add_middleware(TraceMiddleware)
register_exception_handlers(app)
register_profile_exception_handlers(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/llm")
async def health_llm() -> dict[str, object]:
    """Quick check: is LLM enabled and are API keys present?"""
    return {
        "llm_enabled": settings.job_come_llm_enabled,
        "yuai_api_key_set": bool(settings.yuai_api_key),
        "yuai_vision_api_key_set": bool(settings.yuai_vision_api_key),
        "routing_path": settings.job_come_llm_routing_path,
    }


if _docs_enabled:

    @app.get("/docs", include_in_schema=False)
    async def redirect_docs() -> RedirectResponse:
        return RedirectResponse(url=f"{_api_prefix}/docs")

    @app.get("/redoc", include_in_schema=False)
    async def redirect_redoc() -> RedirectResponse:
        return RedirectResponse(url=f"{_api_prefix}/redoc")


app.include_router(api_router, prefix=settings.job_come_api_prefix)
