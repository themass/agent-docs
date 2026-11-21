"""DeerFlow Gateway HTTP client (v2.2.0, verified against the vendored source; see docs/handoff/A-parts/S3.md).

* Thread-scoped run creation ``POST /api/threads/{thread_id}/runs`` is used instead of the stateless
  ``POST /api/runs/stream``: only the thread-scoped routes honour ``Idempotency-Key`` (thread_runs.py),
  and a background run needs no held-open SSE connection.
* Auth: the deployment value of ``DEERFLOW_GATEWAY_TOKEN`` is the gateway's ``DEER_FLOW_INTERNAL_AUTH_TOKEN``
  and goes in ``X-DeerFlow-Internal-Token`` (internal_auth.py:14, auth_middleware.py:98). ``Authorization:
  Bearer`` only works for a ``dfp_`` personal access token minted inside the gateway (pat.py), so it is
  used only when the token has that prefix. The internal token bypasses the PAT route allowlist, which
  makes it more sensitive than ``POETRY_WORKER_TOKEN``. No header when the gateway runs auth-disabled.
* CSRF: ``CSRFMiddleware`` is NOT bypassed by the internal token (csrf_middleware.py:231 skips only when an
  ``Authorization`` header is present; the upstream IM manager says so at channels/manager.py:2299-2310 and
  sends the pair itself), contrary to API.md. So internal-mode POST/PUT/DELETE carry a matching
  ``X-CSRF-Token`` header and ``csrf_token`` cookie (double-submit: equality is all that is checked).
* No model credential exists in this process; the gateway holds them.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Any

import httpx

from agent_worker.governance import UpstreamError

_THREAD_OK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class DeerFlowError(UpstreamError):
    def __init__(self, reason: str, *, retryable: bool, status: int | None = None) -> None:
        super().__init__("deerflow", reason, retryable=retryable, status=status)


@dataclass(frozen=True)
class DeerFlowConfig:
    base_url: str
    token: str = ""
    assistant_id: str = "poetry-editor-lead"
    auth_mode: str = "auto"  # auto | bearer | internal | none
    owner_user_id: str = "poetry-authoring"
    fallback_model: str = ""
    timeout: float = 30.0

    def resolved_mode(self) -> str:
        if self.auth_mode in ("bearer", "internal", "none"):
            return self.auth_mode
        if not self.token:
            return "none"
        return "bearer" if self.token.startswith("dfp_") else "internal"

    def headers(self) -> dict[str, str]:
        mode = self.resolved_mode()
        if mode == "bearer" and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        if mode == "internal" and self.token:
            return {"X-DeerFlow-Internal-Token": self.token, "X-DeerFlow-Owner-User-Id": self.owner_user_id}
        return {}


def thread_id_for(run_id: str) -> str:
    """One thread per run: no history bleeds between runs, and ``multitask_strategy=reject`` never collides."""
    candidate = f"poetry-{run_id}"
    if _THREAD_OK.fullmatch(candidate):
        return candidate
    import hashlib
    return "poetry-" + hashlib.sha1(run_id.encode()).hexdigest()[:40]


class DeerFlowClient:
    def __init__(self, config: DeerFlowConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        self._client = httpx.Client(timeout=config.timeout, transport=transport)
        self._csrf = secrets.token_urlsafe(32)

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None,
                 body: Any = None, extra_headers: dict[str, str] | None = None) -> Any:
        headers = {**self.config.headers(), **(extra_headers or {})}
        if self.config.resolved_mode() == "internal" and method in ("POST", "PUT", "PATCH", "DELETE"):
            headers["X-CSRF-Token"] = self._csrf
            headers["Cookie"] = f"csrf_token={self._csrf}"
        try:
            response = self._client.request(method, f"{self.config.base_url}{path}", params=params, json=body, headers=headers)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise DeerFlowError("NETWORK", retryable=True) from None
        except httpx.TimeoutException:
            raise DeerFlowError("TIMEOUT", retryable=True) from None
        except httpx.HTTPError:
            raise DeerFlowError("NETWORK", retryable=True) from None
        code = response.status_code
        if code in (401, 403):
            raise DeerFlowError("AUTH_FAILED", retryable=False, status=code)
        if code == 404:
            raise DeerFlowError("NOT_FOUND", retryable=False, status=code)
        if code == 409:
            raise DeerFlowError("CONFLICT", retryable=False, status=code)
        if code == 429 or code >= 500:
            raise DeerFlowError(f"HTTP_{code}", retryable=True, status=code)
        if code >= 400:
            raise DeerFlowError("REJECTED", retryable=False, status=code)
        if code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise DeerFlowError("BAD_JSON", retryable=True, status=code) from None

    # ---- operations ----------------------------------------------------------------------------
    def ping(self) -> bool:
        """``/health`` is a public path (auth_middleware.py:37)."""
        try:
            response = self._client.get(f"{self.config.base_url}/health", headers=self.config.headers())
            return response.status_code < 500
        except httpx.HTTPError:
            return False

    def ensure_thread(self, thread_id: str, metadata: dict[str, Any]) -> None:
        """Idempotent for a caller-chosen id (threads.py create_thread)."""
        self._request("POST", "/api/threads", body={
            "thread_id": thread_id, "assistant_id": self.config.assistant_id, "metadata": metadata,
        })

    def create_run(self, thread_id: str, body: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        result = self._request("POST", f"/api/threads/{self._seg(thread_id)}/runs", body=body,
                               extra_headers={"Idempotency-Key": idempotency_key})
        if not isinstance(result, dict) or not result.get("run_id"):
            raise DeerFlowError("BAD_JSON", retryable=True)
        return result

    def get_run(self, thread_id: str, run_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/api/threads/{self._seg(thread_id)}/runs/{self._seg(run_id)}")
        if not isinstance(result, dict) or "status" not in result:
            raise DeerFlowError("BAD_JSON", retryable=True)
        return result

    def list_messages(self, thread_id: str, run_id: str, after_seq: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": 200}
        if after_seq:
            params["after_seq"] = after_seq
        result = self._request("GET", f"/api/threads/{self._seg(thread_id)}/runs/{self._seg(run_id)}/messages", params=params)
        rows = result.get("data") if isinstance(result, dict) else None
        if not isinstance(rows, list):
            raise DeerFlowError("BAD_JSON", retryable=True)
        return [r for r in rows if isinstance(r, dict)]

    def cancel(self, thread_id: str, run_id: str) -> None:
        self._request("POST", f"/api/threads/{self._seg(thread_id)}/runs/{self._seg(run_id)}/cancel",
                      params={"action": "interrupt"})

    @staticmethod
    def _seg(value: str) -> str:
        if not _SAFE_SEGMENT.fullmatch(value):
            raise DeerFlowError("INVALID_ID", retryable=False)
        return value
