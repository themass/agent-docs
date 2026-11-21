"""BFF → agent-worker dispatch client (A-contract §8). The worker owns run execution."""
from __future__ import annotations

import os
from typing import Any

import httpx


class WorkerError(RuntimeError):
    pass


class WorkerClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("POETRY_WORKER_URL", "").rstrip("/")
        self.token = os.getenv("POETRY_WORKER_TOKEN", "")
        self.timeout = float(os.getenv("POETRY_WORKER_TIMEOUT_SECONDS", "10"))

    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured():
            raise WorkerError("agent-worker is not configured (POETRY_WORKER_URL / POETRY_WORKER_TOKEN)")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}{path}",
                    headers={"X-Poetry-Worker-Token": self.token},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise WorkerError(f"agent-worker unavailable: {exc}") from exc
        if not response.is_success:
            raise WorkerError(f"agent-worker rejected the request ({response.status_code})")
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/internal/dispatch", payload)

    def cancel(self, run_id: str) -> dict[str, Any]:
        return self._post(f"/internal/runs/{run_id}/cancel", {})
