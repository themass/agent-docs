"""agent-worker HTTP surface (contract section 8). ``python -m agent_worker.app`` serves on $PORT (8102)."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field

from agent_worker.config import Settings, load_settings
from agent_worker.control import ControlClient
from agent_worker.deerflow.client import DeerFlowClient, DeerFlowConfig
from agent_worker.deerflow.runtime import DeerFlowRuntime
from agent_worker.governance import CircuitBreaker, SystemClock
from agent_worker.runner import DispatchRequest, Runner

log = logging.getLogger("agent_worker.app")
RUN_ID = r"^run_[A-Za-z0-9_-]{1,120}$"


class DispatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=RUN_ID)
    task_id: str = Field(pattern=r"^task_[A-Za-z0-9_-]{1,120}$")
    mandate_id: str = Field(pattern=r"^mandate_[A-Za-z0-9_-]{1,120}$")
    work_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,127}$")
    task_type: Literal["GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"]
    instructions: str = Field(max_length=8000)
    runtime: Literal["DEERFLOW", "STUB"]
    profile_fingerprint: str = Field(min_length=1, max_length=128)
    actor_role: Literal["CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN"]


def build_runner(settings: Settings) -> tuple[Runner, ControlClient, DeerFlowClient | None]:
    control = ControlClient(settings.control_url, settings.control_token, timeout=settings.control_timeout)
    clock = SystemClock()
    breaker = CircuitBreaker(3, 120.0, clock)
    df_client: DeerFlowClient | None = None
    runtime: DeerFlowRuntime | None = None
    if settings.deerflow_enabled and settings.deerflow_url:
        df_client = DeerFlowClient(DeerFlowConfig(
            base_url=settings.deerflow_url, token=settings.deerflow_token,
            assistant_id=settings.deerflow_assistant_id, auth_mode=settings.deerflow_auth_mode,
            owner_user_id=settings.deerflow_owner_user_id, fallback_model=settings.deerflow_fallback_model,
            timeout=settings.deerflow_timeout))
        runtime = DeerFlowRuntime(df_client, breaker, clock)
    return Runner(settings, control, runtime, breaker=breaker, clock=clock), control, df_client


def create_app(
    settings: Settings | None = None,
    runner: Runner | None = None,
    control: ControlClient | None = None,
    deerflow_client: DeerFlowClient | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    if runner is None:
        runner, control, deerflow_client = build_runner(settings)
    assert control is not None

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        runner.shutdown()

    app = FastAPI(title="Poetry Agent Worker", version="0.2.0", lifespan=lifespan)

    def require_token(x_poetry_worker_token: str | None = Header(default=None)) -> None:
        if not settings.worker_token:
            raise HTTPException(503, "worker token is not configured")  # fail closed
        if not x_poetry_worker_token or not hmac.compare_digest(x_poetry_worker_token, settings.worker_token):
            raise HTTPException(401, "worker authorization required")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok", "service": "agent-worker"}

    @app.get("/health/ready")
    def ready() -> dict[str, Any]:
        bridge = control.configured()
        reachable = control.ping() if bridge else False
        df_enabled = settings.deerflow_enabled
        df_reachable = bool(df_enabled and deerflow_client is not None and deerflow_client.ping())
        breaker = runner.breaker.state if df_enabled else "n/a"
        return {
            "status": "ready" if (reachable and settings.worker_token) else "not_ready",
            "service": "agent-worker",
            "deerflow": {"enabled": df_enabled, "reachable": df_reachable, "circuit": breaker},
            "control_bridge": {"configured": bridge, "reachable": reachable},
            "worker_token_configured": bool(settings.worker_token),
            "active_runs": runner.active_runs,
        }

    @app.post("/internal/dispatch", status_code=202, dependencies=[Depends(require_token)])
    def dispatch(body: DispatchBody) -> Any:
        outcome = runner.dispatch(DispatchRequest(**body.model_dump()))
        if outcome == "duplicate":
            from fastapi.responses import JSONResponse
            return JSONResponse({"accepted": True, "duplicate": True}, status_code=200)
        if outcome == "busy":
            raise HTTPException(429, "worker is at capacity; retry later")
        return {"accepted": True}

    @app.post("/internal/runs/{run_id}/cancel", dependencies=[Depends(require_token)])
    def cancel(run_id: str = Path(pattern=RUN_ID)) -> dict[str, Any]:
        return runner.cancel(run_id)

    return app


def run() -> None:
    settings = load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log.info("starting agent-worker %s", settings.public())
    import os

    uvicorn.run(create_app(settings), host=os.getenv("HOST", "0.0.0.0"), port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
