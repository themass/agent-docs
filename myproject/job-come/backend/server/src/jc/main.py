"""JC API entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from agentkit.common.logging import configure_logging
from agentkit.observability import (
    CONTENT_TYPE,
    configure as configure_metrics,
    render_metrics,
)
from agentkit.web import TraceMiddleware
from fastapi import FastAPI
from fastapi import Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError

from jc.api.auth_router import register_exception_handlers
from jc.redis_client import get_session_store
from jc.api.openapi import OPENAPI_TAGS, attach_openapi
from jc.api.profile_router import register_profile_exception_handlers
from jc.api.router import api_router
from jc.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(json_logs=settings.jc_log_json, level=settings.jc_log_level)
    # One call names this deployment on every series. Without it, two JC
    # environments scraped by one Prometheus are indistinguishable.
    configure_metrics(
        application="job-come",
        environment=settings.jc_env,
        enabled=settings.jc_metrics_enabled,
    )
    # A multi-worker backend is several independent registries. Without a shared
    # directory a scrape returns one worker's counters as if they were the
    # service's — the dashboard renders, and it is wrong by a factor of the
    # worker count. `main.py` exports the mode so /admin/metrics can say which
    # one is in effect, rather than leaving an operator to guess.
    metrics_multiprocess = False
    if settings.jc_metrics_multiprocess_dir:
        from agentkit.observability import enable_multiprocess

        metrics_multiprocess = enable_multiprocess(settings.jc_metrics_multiprocess_dir)
        if not metrics_multiprocess:
            logger.warning(
                "JC_METRICS_MULTIPROCESS_DIR is set but sharing is not active; "
                "counters are per-worker"
            )
    from jc.observability.logging_setup import configure_application_logging

    configure_application_logging(json_logs=settings.jc_log_json, level=settings.jc_log_level)
    from jc.config import warn_retired_env

    # Logged at startup rather than left to be noticed: a retired model name in
    # .env reads as the setting that picks the model, and editing it changes
    # nothing at all.
    for message in warn_retired_env():
        logger.warning("retired configuration: %s", message)

    from jc.llm.bootstrap import configure_litellm
    from jc.observability.langfuse_setup import setup_langfuse_callbacks

    configure_litellm()
    setup_langfuse_callbacks()
    from jc.services.mock_report_queue import run_mock_report_dispatcher
    from jc.tasks import run_profile_parse_dispatcher

    # The source table is the durable queue. Every API instance may poll it;
    # database lease claims ensure one instance owns each parse attempt. Mock-interview reports
    # work the same way: the session row is the queue (see jc.services.mock_report_queue).
    dispatchers = [
        asyncio.create_task(run_profile_parse_dispatcher()),
        asyncio.create_task(run_mock_report_dispatcher()),
    ]

    # Build the agent graphs now, not on the first user turn: a cold build costs
    # 4-8 s and would land on whoever messages first after a deploy. Runs in a
    # worker thread so startup is not blocked, and never raises into the app.
    if settings.jc_deerflow_prewarm:
        async def _prewarm() -> None:
            from jc.adapters.deerflow_harness_client import prewarm_entry_clients

            try:
                warmed = await asyncio.to_thread(prewarm_entry_clients)
                logger.info("agent prewarm: %s", ", ".join(warmed) or "nothing")
            except Exception:  # noqa: BLE001
                logger.warning("agent prewarm failed", exc_info=True)

        prewarm_task = asyncio.create_task(_prewarm())
        dispatchers.append(prewarm_task)
    # Listen for session revocations so a logout in one worker takes effect in
    # this one immediately, not after the local cache TTL. Without a listener the
    # cache would keep a logged-out session valid for up to
    # JC_SESSION_CACHE_SECONDS — that is a security window, not a latency detail.
    session_store = get_session_store()
    await session_store.start()

    # The audit writer: model-call rows are queued and written here, off the
    # request path. Started before any traffic so the first turn's rows land.
    from jc.llm.call_log import start_audit_writer, stop_audit_writer

    await start_audit_writer()

    try:
        yield
    finally:
        await stop_audit_writer()
        await session_store.stop()
        for dispatcher in dispatchers:
            dispatcher.cancel()
        for dispatcher in dispatchers:
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


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus scrape endpoint.

    Unauthenticated by design, matching every other /metrics in the ecosystem:
    Prometheus cannot send a session cookie. It therefore carries no user data —
    only counts and durations by scenario/model/phase. If the deployment exposes
    this beyond the private network, restrict it at the proxy rather than adding
    auth the scraper cannot satisfy.
    """
    return Response(content=render_metrics(), media_type=CONTENT_TYPE)


@app.get("/metrics/snapshot", include_in_schema=False)
async def metrics_snapshot() -> JSONResponse:
    """The same metrics as JSON, for the admin dashboard.

    Same registry, same names, same numbers as `/metrics` — only the encoding
    differs. A dashboard therefore cannot drift from what Prometheus sees, and
    a service without a scraper still gets a chartable view.

    Unauthenticated like `/metrics`, for the same reason: a multi-service
    dashboard polls every service with one fetch, and the payload holds counts
    and durations only — never a user id, session id, prompt, or error message.
    `pid` and `host` are here so a client can tell two worker processes apart
    instead of silently summing them.
    """
    from agentkit.observability import snapshot

    from agentkit.observability import sharing_across_processes

    payload = snapshot()
    # Read at request time, not captured at startup: `lifespan` runs in this
    # process but its locals are not visible here, and the first version of this
    # endpoint referenced one and returned 500 on every call.
    payload["sharing_across_processes"] = sharing_across_processes()
    return JSONResponse(payload)


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
