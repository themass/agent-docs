"""BFF-to-MCP control adapter.

The BFF never receives the Java internal token and never talks to MySQL. The MCP control bridge is
its only route to durable Agent orchestration and DRAFT-only content decisions.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlencode

import httpx

from agent_bff.normalize import normalize_keys

log = logging.getLogger("agent_bff.domain")

class DomainControlError(RuntimeError):
    """The bridge or Java could not be used (down, misconfigured, malformed answer)."""


class DomainControlRejected(DomainControlError):
    """Java understood the request and refused it (400/409/422): the caller can act on ``reason``.

    A subclass of DomainControlError so older ``except DomainControlError`` code still works, but
    handlers that care catch this one first and answer 409/422 instead of pretending the service is down.
    """

    def __init__(self, message: str, *, status_code: int, reason: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


def _reason(result: Any) -> str:
    """Dig the human-readable reason out of the bridge/Java envelopes (they nest ``data`` twice)."""
    for _ in range(3):
        if not isinstance(result, dict):
            break
        value = result.get("reason")
        if isinstance(value, str) and value:
            return value[:500]
        result = result.get("data")
    return "rejected by the domain service"


class DomainControlClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("POETRY_DOMAIN_CONTROL_URL", "").rstrip("/")
        self.token = os.getenv("POETRY_DOMAIN_CONTROL_TOKEN", "")
        # 评审/应用是人的决定。worker 只持有 control 令牌，所以它无法批准自己产出的提案（A-05）。
        # 两个令牌都不设时该路由 503：宁可不做，也不能悄悄用 control 令牌代替人的授权。
        self.review_token = os.getenv("POETRY_DOMAIN_REVIEW_TOKEN", "")
        self.timeout = float(os.getenv("POETRY_DOMAIN_CONTROL_TIMEOUT_SECONDS", "15"))

    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _human(self, action: str) -> dict[str, str]:
        """The review token, or a refusal. Never falls back to the control token: that is the whole point."""
        if not self.review_token:
            log.error("POETRY_DOMAIN_REVIEW_TOKEN is not configured; refusing to %s a proposal", action)
            raise DomainControlError("评审通道未配置（POETRY_DOMAIN_REVIEW_TOKEN），无法执行人的评审动作。")
        return {"X-Poetry-Domain-Review-Token": self.review_token}

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"X-Poetry-Domain-Control-Token": self.token}
        if extra:
            headers.update(extra)
        return headers

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None,
                extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
        if not self.configured():
            log.error("Poetry Domain control bridge is not configured (POETRY_DOMAIN_CONTROL_URL / _TOKEN)")
            raise DomainControlError("领域服务通道未配置,请联系管理员。")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(extra_headers),
                    json=payload,
                )
        except httpx.HTTPError as exc:
            log.warning("control bridge unavailable: %s", str(exc)[:300])  # may name internal hosts: log only
            raise DomainControlError("领域服务暂时不可用,请稍后重试。") from exc
        try:
            result = response.json()
        except ValueError:
            result = {"raw": response.text[:2000]}
        if not response.is_success:
            if response.status_code in (400, 409, 422):
                raise DomainControlRejected(
                    f"领域服务拒绝了请求({response.status_code}):{_reason(result)}",
                    status_code=response.status_code, reason=_reason(result))
            log.warning("control bridge answered %s: %s", response.status_code, str(result)[:300])
            raise DomainControlError("领域服务返回了意外的结果,请稍后重试或联系管理员。")
        if not isinstance(result, dict):
            log.warning("control bridge returned a non-object response")
            raise DomainControlError("领域服务返回了无法识别的结果。")
        # Java records may serialise as camelCase; callers only ever see snake_case.
        result = normalize_keys(result)
        if result.get("status") in {"DOMAIN_API_UNAVAILABLE", "DOMAIN_API_REJECTED", "REJECTED", "CONFLICT"}:
            if result.get("status") in {"REJECTED", "CONFLICT"}:
                raise DomainControlRejected(
                    f"领域服务拒绝了请求:{_reason(result)}",
                    status_code=409 if result.get("status") == "CONFLICT" else 422, reason=_reason(result))
            log.warning("domain API unavailable or rejected the bridge call: %s", str(result)[:300])
            raise DomainControlError("领域服务暂时不可用,请稍后重试。")
        return result

    def post(self, path: str, payload: dict[str, Any], extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
        return self.request("POST", path, payload, extra_headers=extra_headers)

    def put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", path, payload)

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]: return self.post("/internal/tasks", payload)
    def get_task(self, task_id: str) -> dict[str, Any]: return self.get(f"/internal/tasks/{task_id}")
    def create_run(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]: return self.post(f"/internal/tasks/{task_id}/runs", payload)
    def get_run(self, run_id: str) -> dict[str, Any]: return self.get(f"/internal/runs/{run_id}")
    def admit_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]: return self.put(f"/internal/runs/{run_id}/admission", payload)
    def change_run_state(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]: return self.put(f"/internal/runs/{run_id}/state", payload)
    def append_event(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]: return self.post(f"/internal/runs/{run_id}/events", payload)
    def events(self, run_id: str, after_event_id: int) -> dict[str, Any]: return self.get(f"/internal/runs/{run_id}/events?after_event_id={after_event_id}")
    def get_proposal(self, proposal_id: str) -> dict[str, Any]: return self.get(f"/internal/proposals/{proposal_id}")

    # ---- read-only lists and views (A-contract §4); every value is URL-encoded here and re-validated by the bridge
    @staticmethod
    def _query(params: dict[str, Any]) -> str:
        kept = {key: str(value) for key, value in params.items() if value is not None and value != ""}
        return f"?{urlencode(sorted(kept.items()))}" if kept else ""

    def list_tasks(self, **params: Any) -> dict[str, Any]: return self.get("/internal/tasks" + self._query(params))
    def task_runs(self, task_id: str) -> dict[str, Any]: return self.get(f"/internal/tasks/{task_id}/runs")
    def list_proposals(self, **params: Any) -> dict[str, Any]: return self.get("/internal/proposals" + self._query(params))
    def proposal_items(self, proposal_id: str) -> dict[str, Any]: return self.get(f"/internal/proposals/{proposal_id}/items")
    def list_works(self, **params: Any) -> dict[str, Any]: return self.get("/internal/works" + self._query(params))
    def work_coverage(self, work_id: str) -> dict[str, Any]: return self.get(f"/internal/works/{work_id}/coverage")
    def work_studio_view(self, work_id: str) -> dict[str, Any]: return self.get(f"/internal/works/{work_id}/studio-view")
    def list_sources(self, **params: Any) -> dict[str, Any]: return self.get("/internal/sources" + self._query(params))

    def persist_proposal(self, *, proposal_id: str, work_id: str, run_id: str, mandate_id: str, actor_role: str, proposal: dict[str, Any]) -> dict[str, Any]:
        return self.post("/internal/proposals", {"proposal_id": proposal_id, "work_id": work_id, "run_id": run_id, "mandate_id": mandate_id, "actor_role": actor_role, "idempotency_key": f"bff:create-proposal:{proposal_id}", "proposal": proposal})

    def apply_proposal(self, *, proposal_id: str, work_id: str, run_id: str, mandate_id: str, review_id: str) -> dict[str, Any]:
        return self.request("POST", f"/internal/proposals/{proposal_id}/apply",
                            {"work_id": work_id, "run_id": run_id, "mandate_id": mandate_id,
                             "actor_role": "CONTENT_EDITOR",
                             "idempotency_key": f"bff:apply-proposal:{proposal_id}:{review_id}",
                             "review_id": review_id},
                            extra_headers=self._human("apply"))

    def record_review(self, *, proposal_id: str, work_id: str, run_id: str, mandate_id: str, actor_role: str, review_id: str, reviewer_id: str, decision: str, comment: str) -> dict[str, Any]:
        return self.request("POST", f"/internal/proposals/{proposal_id}/reviews",
                            {"work_id": work_id, "run_id": run_id, "mandate_id": mandate_id,
                             "actor_role": actor_role, "idempotency_key": f"bff:review-proposal:{review_id}",
                             "review_id": review_id, "reviewer_id": reviewer_id,
                             "decision": decision, "comment": comment},
                            extra_headers=self._human("review"))
