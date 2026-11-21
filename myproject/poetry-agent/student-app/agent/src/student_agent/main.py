"""HTTP entry. Two routes: GET /agent/v1/health and POST /agent/v1/turn.

The turn route always answers 200 with a valid body once the request parses; every model, network or
budget problem is a scripted answer plus ``degraded_reason``. Access logs are off because they would
record client addresses; the service logs turn metadata itself (service.py).
"""
from __future__ import annotations

import hashlib
import logging
import time

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .budget import bucket_for
from .config import Settings
from .models import TurnRequest, TurnResponse
from .service import TurnService

API_PREFIX = "/agent/v1"
AUTH_CACHE_SECONDS = 300.0
MAX_BODY_BYTES = 16 * 1024


def create_app(settings: Settings | None = None, service: TurnService | None = None) -> FastAPI:
    s = settings or Settings.from_env()
    svc = service or TurnService(s)
    app = FastAPI(title="student-agent", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def _limit_body(request: Request, call_next):
        # A turn is a short sentence plus a few ids: 16 KB is generous and bounds what any stage can be handed (B-18).
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "request too large"}, status_code=413)
        return await call_next(request)
    app.add_middleware(CORSMiddleware, allow_origins=list(s.cors), allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type"], allow_credentials=False, max_age=600)
    verified: dict[str, float] = {}

    def authenticate(authorization: str | None) -> str:
        """Bucket key for budgets. In ``java`` auth mode the bearer key must be a real device (cached 5 min)."""
        if s.auth != "java":
            return bucket_for(authorization)
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing or invalid credentials")
        digest = hashlib.sha256(authorization.encode()).hexdigest()
        now = time.monotonic()
        if verified.get(digest, 0.0) > now:
            return digest[:16]
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{s.java_base}/api/student/v1/devices/me", headers={"Authorization": authorization})
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="device check unavailable") from exc
        if res.status_code != 200:
            raise HTTPException(status_code=401, detail="missing or invalid credentials")
        if len(verified) > 5000:
            verified.clear()
        verified[digest] = now + AUTH_CACHE_SECONDS
        return digest[:16]

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, object]:
        return s.health()

    @app.post(f"{API_PREFIX}/turn", response_model=TurnResponse)
    def turn(req: TurnRequest, request: Request, authorization: str | None = Header(default=None)) -> TurnResponse:
        if s.auth != "java" and not authorization:
            # No device credential and no Java to check one against: budgets are per client address, not one shared
            # bucket for the whole class (review P1-2 / B-14).
            host = request.client.host if request.client else "unknown"
            return svc.handle(req, f"ip:{host}")
        return svc.handle(req, authenticate(authorization))

    return app


def run() -> None:  # pragma: no cover - process entry
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    s = Settings.from_env()
    refusal = s.binding_error()
    if refusal:
        raise SystemExit(refusal)
    uvicorn.run(create_app(s), host=s.host, port=s.port, access_log=False, log_level="warning")


app = None  # the app is built by create_app()/run(); no import-time side effects
