"""Client for the MCP control bridge (contract section 4). The worker's only route to Java.

* reads: ``/internal/works/{id}/studio-view`` (fallback: ``snapshot`` + ``gap-report``);
* writes: events, run state, admission, and the proposal (``POST /internal/proposals``).

The bridge does not normalise Java key styles, so responses are returned raw and ``SnapshotView``
normalises them. Retries are bounded; an event POST is retried only when it provably did not reach the
bridge (connect failure / 503), because a duplicated event is worse than a lost one.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from agent_worker.governance import UpstreamError
from agent_worker.vocab import CONTROL_ROLES

_WORK_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,127}$")
_RUN_ID = re.compile(r"^run_[A-Za-z0-9_-]{1,120}$")
_MANDATE_ID = re.compile(r"^mandate_[A-Za-z0-9_-]{1,120}$")
_ERROR_STATUSES = {"DOMAIN_API_UNAVAILABLE": True, "DOMAIN_API_REJECTED": False, "REJECTED": False, "CONFLICT": False}
BACKOFF = (0.5, 1.5)


class ControlError(UpstreamError):
    def __init__(self, reason: str, *, retryable: bool, status: int | None = None) -> None:
        super().__init__("control", reason, retryable=retryable, status=status)


def control_role(dispatch_role: str) -> str:
    """The bridge/MCP accept only two roles; others act as CONTENT_EDITOR. The role is audit context,
    never an authorisation decision (Java authenticates the service principal)."""
    return dispatch_role if dispatch_role in CONTROL_ROLES else "CONTENT_EDITOR"


def proposal_id_for(run_id: str) -> str:
    return "proposal_" + (run_id.removeprefix("run_"))


def unwrap_envelope(body: Any) -> dict[str, Any]:
    """Raise on a rejected/unavailable Java envelope; otherwise return the dict untouched."""
    if not isinstance(body, dict):
        raise ControlError("BAD_JSON", retryable=True)
    status = body.get("status")
    if isinstance(status, str) and status in _ERROR_STATUSES:
        raise ControlError(status, retryable=_ERROR_STATUSES[status])
    return body


class ControlClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._sleep = sleep
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def configured(self) -> bool:
        return bool(self.base_url and self._token)

    def close(self) -> None:
        self._client.close()

    # ---- transport -----------------------------------------------------------------------------
    def _once(self, method: str, path: str, params: dict[str, str] | None, body: Any) -> dict[str, Any]:
        if not self.configured():
            raise ControlError("NOT_CONFIGURED", retryable=False)
        try:
            response = self._client.request(
                method, f"{self.base_url}{path}", params=params, json=body,
                headers={"X-Poetry-Domain-Control-Token": self._token},
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise ControlError("NETWORK", retryable=True) from None
        except httpx.TimeoutException:
            raise ControlError("TIMEOUT", retryable=True) from None
        except httpx.HTTPError:
            raise ControlError("NETWORK", retryable=True) from None
        code = response.status_code
        if code >= 500 or code == 429:
            raise ControlError(f"HTTP_{code}", retryable=True, status=code)
        if code >= 400:
            raise ControlError(f"HTTP_{code}", retryable=False, status=code)
        try:
            return unwrap_envelope(response.json())
        except ValueError:
            raise ControlError("BAD_JSON", retryable=True) from None

    def request(
        self, method: str, path: str, *, params: dict[str, str] | None = None, body: Any = None,
        replay_safe: bool = True,
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                return self._once(method, path, params, body)
            except ControlError as exc:
                attempt += 1
                safe = exc.retryable and (replay_safe or exc.reason in {"NETWORK", "HTTP_503"})
                if not safe or attempt > len(BACKOFF):
                    raise
                self._sleep(BACKOFF[attempt - 1])

    # ---- reads ---------------------------------------------------------------------------------
    def ping(self) -> bool:
        try:
            self._once("GET", "/internal/works", {"limit": "1"}, None)
            return True
        except ControlError:
            return False

    def get_studio_view(self, work_id: str) -> dict[str, Any]:
        self._check_ids(work_id=work_id)
        return self.request("GET", f"/internal/works/{work_id}/studio-view")

    def get_snapshot(self, work_id: str, run_id: str, mandate_id: str) -> dict[str, Any]:
        self._check_ids(work_id=work_id, run_id=run_id, mandate_id=mandate_id)
        return self.request("GET", f"/internal/works/{work_id}/snapshot",
                            params={"run_id": run_id, "mandate_id": mandate_id})

    def get_gap_report(self, work_id: str, run_id: str, mandate_id: str) -> dict[str, Any]:
        self._check_ids(work_id=work_id, run_id=run_id, mandate_id=mandate_id)
        return self.request("GET", f"/internal/works/{work_id}/gap-report",
                            params={"run_id": run_id, "mandate_id": mandate_id})

    def load_context(
        self, work_id: str, run_id: str, mandate_id: str,
        on_call: Callable[[str, str, int], None] | None = None,
    ) -> dict[str, Any]:
        """studio-view, or (older bridge) snapshot + gap-report merged into the same shape."""
        def timed(tool: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
            t0 = time.monotonic()
            try:
                result = fn()
            except ControlError as exc:
                if on_call:
                    on_call(tool, f"error:{exc.reason}", int((time.monotonic() - t0) * 1000))
                raise
            if on_call:
                on_call(tool, "ok", int((time.monotonic() - t0) * 1000))
            return result

        try:
            return timed("studio_view", lambda: self.get_studio_view(work_id))
        except ControlError as exc:
            if exc.status not in (404, 405):
                raise
        snap = timed("snapshot", lambda: self.get_snapshot(work_id, run_id, mandate_id))
        gaps = timed("gap_report", lambda: self.get_gap_report(work_id, run_id, mandate_id))
        data = dict(snap.get("data") if isinstance(snap.get("data"), dict) else snap)
        data["gap_report"] = gaps.get("data") if isinstance(gaps.get("data"), dict) else gaps
        return {"data": data, "status": "OK"}

    # ---- writes --------------------------------------------------------------------------------
    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self._check_ids(run_id=run_id)
        self.request("POST", f"/internal/runs/{run_id}/events",
                     body={"event_type": event_type, "payload": payload}, replay_safe=False)

    def set_state(self, run_id: str, status: str, reason: str | None = None) -> None:
        self._check_ids(run_id=run_id)
        body: dict[str, Any] = {"status": status}
        if reason:
            body["reason"] = reason[:4000]
        self.request("PUT", f"/internal/runs/{run_id}/state", body=body)

    def admit_running(self, run_id: str, thread_id: str, runtime_run_id: str) -> None:
        """DEERFLOW only: record the runtime correlation ids; status stays RUNNING."""
        self._check_ids(run_id=run_id)
        self.request("PUT", f"/internal/runs/{run_id}/admission", body={
            "status": "RUNNING", "runtime_thread_id": thread_id[:128], "runtime_run_id": runtime_run_id[:128],
        })

    def create_proposal(
        self, *, run_id: str, mandate_id: str, work_id: str, actor_role: str, proposal: dict[str, Any],
    ) -> str:
        """Idempotent: key ``worker:proposal:<run_id>``. Returns the proposal id."""
        self._check_ids(work_id=work_id, run_id=run_id, mandate_id=mandate_id)
        proposal_id = proposal_id_for(run_id)
        self.request("POST", "/internal/proposals", body={
            "proposal_id": proposal_id, "work_id": work_id, "run_id": run_id, "mandate_id": mandate_id,
            "actor_role": control_role(actor_role), "idempotency_key": f"worker:proposal:{run_id}",
            "proposal": proposal,
        })
        return proposal_id

    @staticmethod
    def _check_ids(*, work_id: str | None = None, run_id: str | None = None, mandate_id: str | None = None) -> None:
        for value, pattern, name in ((work_id, _WORK_ID, "work_id"), (run_id, _RUN_ID, "run_id"),
                                     (mandate_id, _MANDATE_ID, "mandate_id")):
            if value is not None and not pattern.fullmatch(value):
                raise ControlError(f"INVALID_{name.upper()}", retryable=False)
