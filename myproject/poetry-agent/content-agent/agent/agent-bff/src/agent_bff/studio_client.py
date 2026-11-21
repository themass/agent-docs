"""Direct BFF → Java client for the human-only Studio write endpoints.

These routes (locator entry, source verification, per-item proposal decisions) must never travel
through the MCP control bridge or any agent-reachable process. The reviewer token is held only by
this process and the Java host (A-contract D1).
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from agent_bff.normalize import normalize_keys

log = logging.getLogger("agent_bff.studio")


class StudioError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, code: str = "STUDIO_UNAVAILABLE", details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details


class StudioClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("POETRY_API_BASE_URL", "").rstrip("/")
        self.token = os.getenv("POETRY_STUDIO_REVIEWER_TOKEN", "")
        self.timeout = float(os.getenv("POETRY_API_TIMEOUT_SECONDS", "15"))

    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured():
            log.error("Studio reviewer channel is not configured (POETRY_API_BASE_URL / POETRY_STUDIO_REVIEWER_TOKEN)")
            raise StudioError("人工评审通道未配置,请联系管理员。", status_code=503)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    f"{self.base_url}/api/poetry/v1/studio{path}",
                    headers={"X-Poetry-Studio-Reviewer-Token": self.token},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            log.warning("Java studio endpoint unavailable: %s", str(exc)[:300])  # may name internal hosts: log only
            raise StudioError("人工评审通道暂时不可用,请稍后重试。", status_code=503) from exc
        try:
            body = normalize_keys(response.json())
        except ValueError:
            body = {"raw": response.text[:500]}
        if not isinstance(body, dict):
            body = {"data": body}
        if response.is_success:
            # Java answers either with the AgentResponse envelope or the plain Response wrapper.
            if body.get("status") in {"REJECTED", "CONFLICT"}:
                raise self._rejection(409 if body.get("status") == "CONFLICT" else 422, body)
            return body.get("data") if isinstance(body.get("data"), dict) else body
        raise self._rejection(response.status_code, body)

    @staticmethod
    def _rejection(http_status: int, body: dict[str, Any]) -> StudioError:
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        message = str(body.get("error") or data.get("reason") or body.get("message") or f"HTTP {http_status}")
        details = data or None
        if http_status == 409:
            return StudioError(message, status_code=409, code="STUDIO_CONFLICT", details=details)
        if http_status in (400, 422):
            return StudioError(message, status_code=422, code="STUDIO_REJECTED", details=details)
        if http_status in (401, 403):
            # A wrong or missing reviewer token is a deployment fault, not something the editor can fix.
            return StudioError("reviewer channel authentication failed", status_code=502, code="STUDIO_AUTH_FAILED")
        # Anything else is an upstream fault: its text is for the log, not for the browser.
        log.warning("Java studio endpoint answered %s: %s", http_status, message[:300])
        if http_status == 503:
            return StudioError("人工评审通道暂时不可用,请稍后重试。", status_code=503)
        return StudioError("人工评审通道返回了意外的结果,请稍后重试或联系管理员。", status_code=502)

    def put_locator(self, claim_id: str, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/citations/{claim_id}/{source_id}/locator", payload)

    def verify_source(self, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/sources/{source_id}/verification", payload)

    def put_items(self, proposal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PUT", f"/proposals/{proposal_id}/items", payload)
