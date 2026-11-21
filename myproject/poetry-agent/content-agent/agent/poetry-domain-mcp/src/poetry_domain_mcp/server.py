"""The only MCP boundary allowed to call the Java Poetry API.

This process contains no database driver and exposes no publish/verify/delete tools by design.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

import httpx
import uvicorn
from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

mcp = MCPServer(
    name="poetry-domain",
    instructions=(
        "Use this server only for Poetry authoring-domain reads and DRAFT-only proposals. "
        "It has no publishing, source verification, delete, or SQL capability."
    ),
)


# Ids are minted by agent-bff as "<prefix>_<uuid4 hex>" and are interpolated into URL paths and
# headers. A prefix-only check ("^proposal_") lets "proposal_x/../../audit" or "proposal_x?a=1"
# through to the Java API, so every pattern is fully anchored.
WORK_ID = r"^[a-z0-9][a-z0-9_-]{1,127}$"


def _prefixed(prefix: str) -> str:
    return rf"^{prefix}_[A-Za-z0-9_-]{{1,120}}$"


RUN_ID = _prefixed("run")
MANDATE_ID = _prefixed("mandate")
PROPOSAL_ID = _prefixed("proposal")
REVIEW_ID = _prefixed("review")
TASK_ID = _prefixed("task")

_WORK_ID_RE = re.compile(WORK_ID)
_PATH_ID_RES = {
    "task_id": re.compile(TASK_ID),
    "run_id": re.compile(RUN_ID),
    "proposal_id": re.compile(PROPOSAL_ID),
    "work_id": _WORK_ID_RE,
}


def check_work_id(work_id: str) -> str:
    """Independent of how the MCP SDK validates tool arguments: never build a URL from this unchecked."""
    if not _WORK_ID_RE.fullmatch(work_id):
        raise ValueError("work_id must match " + WORK_ID)
    return work_id


# Java vocabulary (Vocabulary.java). An agent-originated executable annotation may never carry a
# locator (only a human reviewer fills one in) and may never claim KNOWN certainty.
AGENT_AUDIENCES = frozenset({"PRIMARY", "JUNIOR", "SENIOR"})
AGENT_CERTAINTIES = frozenset({"LIKELY", "DISPUTED", "UNKNOWN"})


def check_agent_annotation_payload(payload: dict[str, Any]) -> None:
    if payload.get("locator") not in (None, ""):
        raise ValueError("an agent proposal may not supply a locator; a human reviewer fills it in")
    audience = payload.get("audience")
    if audience is not None and audience not in AGENT_AUDIENCES:
        raise ValueError("audience must be one of " + "|".join(sorted(AGENT_AUDIENCES)))
    certainty = payload.get("certainty")
    if certainty is not None and certainty not in AGENT_CERTAINTIES:
        raise ValueError("certainty from an agent must be one of " + "|".join(sorted(AGENT_CERTAINTIES)))


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=RUN_ID)
    mandate_id: str = Field(pattern=MANDATE_ID)
    actor_role: Literal["CONTENT_EDITOR", "HISTORICAL_REVIEWER"]
    idempotency_key: str = Field(min_length=12, max_length=128)


class DraftProposalRequest(ToolRequest):
    work_id: str = Field(pattern=WORK_ID)
    proposal_id: str | None = Field(default=None, pattern=PROPOSAL_ID)
    proposal: dict[str, Any]

    @field_validator("proposal")
    @classmethod
    def draft_only(cls, proposal: dict[str, Any]) -> dict[str, Any]:
        if proposal.get("status") != "DRAFT":
            raise ValueError("proposal status must be DRAFT")
        # Narrative may legitimately describe a blocked publication state. Inspect executable shape,
        # not arbitrary prose, and leave the Java service to revalidate it authoritatively.
        for change in proposal.get("changes", []):
            payload = change.get("draft_payload")
            if payload is not None and payload.get("operation") != "CREATE_ANNOTATION":
                raise ValueError("only CREATE_ANNOTATION is an executable v1 DRAFT operation")
            if payload is not None:
                check_agent_annotation_payload(payload)
        return proposal


class ApplyApprovedDraftRequest(ToolRequest):
    proposal_id: str = Field(pattern=PROPOSAL_ID)
    review_id: str = Field(pattern=REVIEW_ID)


class CompileRequest(ToolRequest):
    work_id: str = Field(pattern=WORK_ID)
    script_version: str = Field(min_length=1, max_length=128)


def api_base() -> str:
    return os.getenv("POETRY_API_BASE_URL", "").rstrip("/")


async def call_domain(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Forward transparently; lack of Java API is an explicit failure, never a fake success."""
    base = api_base()
    if not base:
        return {
            "status": "DOMAIN_API_UNAVAILABLE",
            "data": {},
            "audit_refs": [],
            "next_action": "HUMAN_REVIEW",
            "reason": "POETRY_API_BASE_URL is not configured",
        }
    headers = {
        "X-Poetry-Agent-Internal-Token": os.getenv("POETRY_AGENT_INTERNAL_TOKEN", ""),
        # The caller-provided role is audit context only. Authorization is the deployment-bound
        # service principal, never an LLM-controlled field in an MCP tool argument.
        "X-Poetry-Agent-Role": os.getenv("POETRY_AGENT_ACTOR_ROLE", "CONTENT_EDITOR"),
        "X-Poetry-Agent-Run-Id": (payload or {}).get("run_id", ""),
        "X-Poetry-Agent-Mandate-Id": (payload or {}).get("mandate_id", ""),
        "Idempotency-Key": (payload or {}).get("idempotency_key", ""),
    }
    request_kwargs: dict[str, Any] = {"headers": headers}
    # GET correlation is header-only: neither agent operational IDs nor request material are
    # placed in a query string or a GET body that intermediary infrastructure might discard.
    if method != "GET":
        request_kwargs["json"] = payload
    try:
        async with httpx.AsyncClient(timeout=float(os.getenv("POETRY_API_TIMEOUT_SECONDS", "15"))) as client:
            response = await client.request(method, f"{base}{path}", **request_kwargs)
    except httpx.HTTPError as exc:
        return {
            "status": "DOMAIN_API_UNAVAILABLE",
            "data": {},
            "audit_refs": [],
            "next_action": "REPLAN",
            "reason": str(exc),
        }
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text[:2000]}
    if not response.is_success:
        return {
            "status": "DOMAIN_API_REJECTED",
            "data": data,
            "audit_refs": [],
            "next_action": "REPLAN",
            "http_status": response.status_code,
        }
    return data if isinstance(data, dict) else {"status": "OK", "data": data, "audit_refs": [], "next_action": "NONE"}


@mcp.tool(name="get_work_snapshot")
async def get_work_snapshot(
    work_id: Annotated[str, Field(pattern=WORK_ID)], request: ToolRequest
) -> dict[str, Any]:
    """Return the canonical content snapshot for one work. Read only."""
    work_id = check_work_id(work_id)
    return await call_domain("GET", f"/api/poetry/v1/works/{work_id}/snapshot", request.model_dump())


@mcp.tool(name="get_integrity_gap_report")
async def get_integrity_gap_report(
    work_id: Annotated[str, Field(pattern=WORK_ID)], request: ToolRequest
) -> dict[str, Any]:
    """Return server-side completeness gaps; it never manufactures facts."""
    work_id = check_work_id(work_id)
    return await call_domain(
        "GET", f"/api/poetry/v1/works/{work_id}/integrity-gap-report", request.model_dump()
    )


@mcp.tool(name="create_draft_proposal")
async def create_draft_proposal(request: DraftProposalRequest) -> dict[str, Any]:
    """Persist a DRAFT-only proposal. It cannot publish or verify a source."""
    return await call_domain("POST", "/api/poetry/v1/draft/proposals", request.model_dump())


@mcp.tool(name="apply_approved_draft")
async def apply_approved_draft(request: ApplyApprovedDraftRequest) -> dict[str, Any]:
    """Request Java API to apply an approved proposal as DRAFT only, with its own state checks."""
    return await call_domain("POST", f"/api/poetry/v1/draft/proposals/{request.proposal_id}/apply", request.model_dump())


@mcp.tool(name="request_compile")
async def request_compile(request: CompileRequest) -> dict[str, Any]:
    """Request Scene Compiler eligibility checking. This is not publication or CDN release."""
    return await call_domain("POST", f"/api/poetry/v1/works/{request.work_id}/compile-requests", request.model_dump())


class OrchestrationTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(pattern=TASK_ID)
    work_id: str = Field(pattern=WORK_ID)
    title: str = Field(min_length=3, max_length=200)
    task_type: Literal["GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"]
    requested_by: str = Field(min_length=1, max_length=100)
    requested_role: Literal["CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN"]
    instructions: str = Field(min_length=1, max_length=8000)
    requested_profile: str = Field(min_length=1, max_length=64)


class OrchestrationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=RUN_ID)
    mandate_id: str = Field(pattern=MANDATE_ID)
    runtime: Literal["DEERFLOW", "STUB"]
    profile_name: str = Field(min_length=1, max_length=64)
    profile_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    profile_manifest: dict[str, Any]


class OrchestrationAdmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["RUNNING", "WAITING_FOR_RUNTIME", "AWAITING_REVIEW", "COMPLETED", "FAILED"]
    runtime_thread_id: str | None = Field(default=None, max_length=128)
    runtime_run_id: str | None = Field(default=None, max_length=128)
    reason: str | None = Field(default=None, max_length=4000)


class OrchestrationStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["RUNNING", "WAITING_FOR_RUNTIME", "AWAITING_REVIEW", "COMPLETED", "FAILED"]
    reason: str | None = Field(default=None, max_length=4000)


class OrchestrationEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProposalReviewForwardRequest(ToolRequest):
    work_id: str = Field(pattern=WORK_ID)
    review_id: str = Field(pattern=REVIEW_ID)
    reviewer_id: str = Field(min_length=1, max_length=128)
    decision: Literal["APPROVE", "REJECT"]
    comment: str = Field(default="", max_length=4000)


class ProposalApplyForwardRequest(ToolRequest):
    work_id: str = Field(pattern=WORK_ID)
    review_id: str = Field(pattern=REVIEW_ID)


def same_secret(provided: str | None, expected: str) -> bool:
    """Constant-time token comparison; an empty expected value never matches (fail closed)."""
    if not expected or provided is None:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def control_authorized(request: Request) -> bool:
    return same_secret(request.headers.get("X-Poetry-Domain-Control-Token"), os.getenv("POETRY_DOMAIN_CONTROL_TOKEN", ""))


def review_authorized(request: Request) -> bool:
    """The human side of a proposal lifecycle, which the worker must never hold (A-05).

    Two separate secrets, checked as separate headers, so a leaked worker token buys "create a proposal"
    and nothing else. Rotating one does not invalidate the other. An unset secret never matches.
    """
    return same_secret(request.headers.get("X-Poetry-Domain-Review-Token"), os.getenv("POETRY_DOMAIN_REVIEW_TOKEN", ""))


def control_gate(request: Request, *, human: bool = False) -> JSONResponse | None:
    """Return a rejection response, or None when the caller may proceed.

    Authorization is checked before anything about the request is revealed. Path ids are then
    validated because they are forwarded into the Java URL.

    ``human=True`` marks the routes that decide a proposal: review and apply. They need the review
    token *in addition to* the control token, so holding the control token (which the worker does) is
    not enough to approve the worker's own output. Without this split an agent token could create a
    proposal, approve it and apply it, bypassing itemised review entirely.
    """
    if not control_authorized(request):
        return JSONResponse({"error": "domain control authorization required"}, status_code=401)
    if human and not review_authorized(request):
        return JSONResponse({"error": "domain review authorization required"}, status_code=401)
    for name, value in request.path_params.items():
        pattern = _PATH_ID_RES.get(name)
        if pattern is not None and not pattern.fullmatch(str(value)):
            return JSONResponse({"error": f"invalid {name}"}, status_code=400)
    return None


async def control_create_proposal(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    try:
        body = DraftProposalRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid control request: {exc}"}, status_code=400)
    result = await call_domain("POST", "/api/poetry/v1/draft/proposals", body.model_dump(exclude_none=True))
    return control_response(result)


async def control_review_proposal(request: Request) -> JSONResponse:
    if (denied := control_gate(request, human=True)) is not None:
        return denied
    proposal_id = request.path_params["proposal_id"]
    try:
        body = ProposalReviewForwardRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid control request: {exc}"}, status_code=400)
    payload = body.model_dump()
    result = await call_domain("POST", f"/api/poetry/v1/draft/proposals/{proposal_id}/reviews", payload)
    return control_response(result)


async def control_apply_proposal(request: Request) -> JSONResponse:
    if (denied := control_gate(request, human=True)) is not None:
        return denied
    proposal_id = request.path_params["proposal_id"]
    try:
        body = ProposalApplyForwardRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid control request: {exc}"}, status_code=400)
    result = await call_domain("POST", f"/api/poetry/v1/draft/proposals/{proposal_id}/apply", body.model_dump())
    return control_response(result)


async def control_create_task(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    try:
        body = OrchestrationTaskRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid orchestration request: {exc}"}, status_code=400)
    return control_response(await call_domain("POST", "/api/poetry/v1/agent-orchestration/tasks", body.model_dump()))


async def control_task(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    return control_response(await call_domain("GET", f"/api/poetry/v1/agent-orchestration/tasks/{request.path_params['task_id']}"))


async def control_create_run(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    try:
        body = OrchestrationRunRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid orchestration request: {exc}"}, status_code=400)
    return control_response(await call_domain("POST", f"/api/poetry/v1/agent-orchestration/tasks/{request.path_params['task_id']}/runs", body.model_dump()))


async def control_run(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    return control_response(await call_domain("GET", f"/api/poetry/v1/agent-orchestration/runs/{request.path_params['run_id']}"))


async def control_admission(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    try:
        body = OrchestrationAdmissionRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid orchestration request: {exc}"}, status_code=400)
    return control_response(await call_domain("PUT", f"/api/poetry/v1/agent-orchestration/runs/{request.path_params['run_id']}/admission", body.model_dump(exclude_none=True)))


async def control_run_state(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    try:
        body = OrchestrationStateRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid orchestration request: {exc}"}, status_code=400)
    return control_response(await call_domain("PUT", f"/api/poetry/v1/agent-orchestration/runs/{request.path_params['run_id']}/state", body.model_dump(exclude_none=True)))


async def control_event(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    try:
        body = OrchestrationEventRequest.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        return JSONResponse({"error": f"invalid orchestration request: {exc}"}, status_code=400)
    return control_response(await call_domain("POST", f"/api/poetry/v1/agent-orchestration/runs/{request.path_params['run_id']}/events", body.model_dump()))


async def control_events(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    after = request.query_params.get("after_event_id", "0")
    # str.isdigit() accepts superscripts and non-Latin digits; only plain ASCII 0-9 is a valid cursor.
    if not (after.isascii() and after.isdigit()):
        return JSONResponse({"error": "after_event_id must be a non-negative integer"}, status_code=400)
    return control_response(await call_domain("GET", f"/api/poetry/v1/agent-orchestration/runs/{request.path_params['run_id']}/events?after_event_id={after}"))


async def control_proposal(request: Request) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    return control_response(await call_domain("GET", f"/api/poetry/v1/agent-orchestration/proposals/{request.path_params['proposal_id']}"))


# --------------------------------------------------------------------------- read-only forwards
# Studio and the worker read lists/views through the control bridge. Every query value is checked
# against an anchored ASCII pattern and re-encoded, so no caller text reaches the Java URL raw.
# Human write endpoints (/api/poetry/v1/studio/*) are deliberately NOT reachable from here.

_Q_LIMIT = re.compile(r"^[0-9]{1,3}$")
_Q_OFFSET = re.compile(r"^[0-9]{1,6}$")
_Q_ENUM = re.compile(r"^[A-Z][A-Z_]{0,31}$")
_QUERY_PATTERNS: dict[str, re.Pattern[str]] = {
    "limit": _Q_LIMIT,
    "offset": _Q_OFFSET,
    "work_id": _WORK_ID_RE,
    "status": _Q_ENUM,
    "task_type": _Q_ENUM,
    "review_status": _Q_ENUM,
    "verification_status": _Q_ENUM,
    "run_id": re.compile(RUN_ID),
    "mandate_id": re.compile(MANDATE_ID),
    "task_id": re.compile(TASK_ID),
}


def _checked_query(request: Request, allowed: set[str], required: set[str] | None = None) -> tuple[str | None, JSONResponse | None]:
    """Return (encoded query string, None) or (None, 400 response)."""
    seen: dict[str, str] = {}
    for key, value in request.query_params.multi_items():
        pattern = _QUERY_PATTERNS.get(key)
        if key not in allowed or pattern is None:
            return None, JSONResponse({"error": f"unsupported query parameter: {key}"}, status_code=400)
        if key in seen:
            return None, JSONResponse({"error": f"duplicate query parameter: {key}"}, status_code=400)
        if not pattern.fullmatch(value):
            return None, JSONResponse({"error": f"invalid {key}"}, status_code=400)
        seen[key] = value
    for key in required or set():
        if key not in seen:
            return None, JSONResponse({"error": f"missing query parameter: {key}"}, status_code=400)
    return urlencode(sorted(seen.items())), None


async def _forward_list(request: Request, java_path: str, allowed: set[str]) -> JSONResponse:
    if (denied := control_gate(request)) is not None:
        return denied
    query, bad = _checked_query(request, allowed)
    if bad is not None:
        return bad
    return control_response(await call_domain("GET", java_path + (f"?{query}" if query else "")))


_ORCH = "/api/poetry/v1/agent-orchestration"
_LIST_QUERY = {"limit", "offset"}


async def control_list_tasks(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/tasks", _LIST_QUERY | {"work_id", "status", "task_type"})


async def control_task_runs(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/tasks/{request.path_params['task_id']}/runs", set())


async def control_list_proposals(request: Request) -> JSONResponse:
    allowed = _LIST_QUERY | {"work_id", "status", "review_status", "run_id", "task_id"}
    return await _forward_list(request, f"{_ORCH}/proposals", allowed)


async def control_proposal_items(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/proposals/{request.path_params['proposal_id']}/items", set())


async def control_list_works(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/works", _LIST_QUERY)


async def control_work_coverage(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/works/{request.path_params['work_id']}/coverage", set())


async def control_work_studio_view(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/works/{request.path_params['work_id']}/studio-view", set())


async def control_list_sources(request: Request) -> JSONResponse:
    return await _forward_list(request, f"{_ORCH}/sources", _LIST_QUERY | {"verification_status"})


async def _forward_agent_read(request: Request, suffix: str) -> JSONResponse:
    """snapshot / gap-report need the Java agent headers (run, mandate, idempotency key)."""
    if (denied := control_gate(request)) is not None:
        return denied
    _query, bad = _checked_query(request, {"run_id", "mandate_id"}, required={"run_id", "mandate_id"})
    if bad is not None:
        return bad
    params = dict(request.query_params)
    if not re.fullmatch(MANDATE_ID, params["mandate_id"]):
        return JSONResponse({"error": "invalid mandate_id"}, status_code=400)
    work_id = request.path_params["work_id"]
    digest = hashlib.sha256(f"{params['run_id']}:{params['mandate_id']}:{work_id}:{suffix}".encode()).hexdigest()[:32]
    envelope = {"run_id": params["run_id"], "mandate_id": params["mandate_id"], "idempotency_key": f"control:read:{digest}"}
    return control_response(await call_domain("GET", f"/api/poetry/v1/works/{work_id}/{suffix}", envelope))


async def control_work_snapshot(request: Request) -> JSONResponse:
    return await _forward_agent_read(request, "snapshot")


async def control_work_gap_report(request: Request) -> JSONResponse:
    return await _forward_agent_read(request, "integrity-gap-report")


def control_response(result: dict[str, Any]) -> JSONResponse:
    """Do not turn a rejected Java request into a successful BFF control call."""
    if result.get("status") == "DOMAIN_API_UNAVAILABLE":
        return JSONResponse(result, status_code=503)
    if result.get("status") == "DOMAIN_API_REJECTED":
        return JSONResponse(result, status_code=int(result.get("http_status", 502)))
    return JSONResponse(result)


class InternalMcpAuth:
    """Reject direct calls unless they carry the deployment-injected service token."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            expected = os.getenv("MCP_INTERNAL_TOKEN", "")
            headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
            if not same_secret(headers.get("authorization"), f"Bearer {expected}" if expected else ""):
                response = JSONResponse({"error": "internal MCP authorization required"}, status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# The module-level ``mcp`` above is the full library of five tools (tests and in-process callers use it).
# What /mcp actually *serves* is narrower: DeerFlow's agent only ever needs to read, and the worker never
# uses /mcp at all (it goes through /internal/*). So by default only the two read tools are exposed, and
# anything wider must be asked for by name. This makes "the agent can only read" a property of the server,
# not just of DeerFlow's allow-list and the token distribution (review item A-12).
TOOL_FUNCTIONS = {
    "get_work_snapshot": get_work_snapshot,
    "get_integrity_gap_report": get_integrity_gap_report,
    "create_draft_proposal": create_draft_proposal,
    "apply_approved_draft": apply_approved_draft,
    "request_compile": request_compile,
}
READ_ONLY_TOOLS = ("get_work_snapshot", "get_integrity_gap_report")


def exposed_tool_names() -> list[str]:
    """Tools served over HTTP: POETRY_MCP_EXPOSED_TOOLS (comma separated) or the read-only default.

    An unknown name aborts startup instead of being ignored: a typo must not silently widen or narrow
    what an agent can call.
    """
    raw = os.getenv("POETRY_MCP_EXPOSED_TOOLS", "").strip()
    if not raw:
        return list(READ_ONLY_TOOLS)
    names = [part.strip() for part in raw.split(",") if part.strip()]
    unknown = [name for name in names if name not in TOOL_FUNCTIONS]
    if unknown or not names:
        raise ValueError(f"POETRY_MCP_EXPOSED_TOOLS names unknown tools: {unknown or raw!r}")
    return names


def build_served_mcp() -> MCPServer:
    served = MCPServer(
        name="poetry-domain",
        instructions=(
            "Read canonical Poetry content for authoring analysis. Tools that write are only available when "
            "the deployment lists them explicitly. This server has no publishing, source verification, "
            "delete, or SQL capability."
        ),
    )
    for name in exposed_tool_names():
        served.add_tool(TOOL_FUNCTIONS[name], name=name)
    return served


def build_app() -> InternalMcpAuth:
    mcp_app = build_served_mcp().streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        host="0.0.0.0",
    )

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        # Starlette's Mount does not forward lifespan events to the app it mounts. The MCP app owns the
        # StreamableHTTP session manager's task group, and without running it every /mcp request fails
        # with "Task group is not initialized" (HTTP 500) even when the token is valid. The control
        # bridge (/internal/*) never touches it, which is why that half worked and hid the fault.
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    app = Starlette(lifespan=lifespan, routes=[
        Route("/internal/tasks", control_create_task, methods=["POST"]),
        Route("/internal/tasks/{task_id}", control_task, methods=["GET"]),
        Route("/internal/tasks/{task_id}/runs", control_create_run, methods=["POST"]),
        Route("/internal/runs/{run_id}", control_run, methods=["GET"]),
        Route("/internal/runs/{run_id}/admission", control_admission, methods=["PUT"]),
        Route("/internal/runs/{run_id}/state", control_run_state, methods=["PUT"]),
        Route("/internal/runs/{run_id}/events", control_event, methods=["POST"]),
        Route("/internal/runs/{run_id}/events", control_events, methods=["GET"]),
        Route("/internal/tasks", control_list_tasks, methods=["GET"]),
        Route("/internal/tasks/{task_id}/runs", control_task_runs, methods=["GET"]),
        Route("/internal/proposals/{proposal_id}", control_proposal, methods=["GET"]),
        Route("/internal/proposals/{proposal_id}/items", control_proposal_items, methods=["GET"]),
        Route("/internal/proposals", control_create_proposal, methods=["POST"]),
        Route("/internal/proposals", control_list_proposals, methods=["GET"]),
        Route("/internal/works", control_list_works, methods=["GET"]),
        Route("/internal/works/{work_id}/coverage", control_work_coverage, methods=["GET"]),
        Route("/internal/works/{work_id}/studio-view", control_work_studio_view, methods=["GET"]),
        Route("/internal/works/{work_id}/snapshot", control_work_snapshot, methods=["GET"]),
        Route("/internal/works/{work_id}/gap-report", control_work_gap_report, methods=["GET"]),
        Route("/internal/sources", control_list_sources, methods=["GET"]),
        Route("/internal/proposals/{proposal_id}/reviews", control_review_proposal, methods=["POST"]),
        Route("/internal/proposals/{proposal_id}/apply", control_apply_proposal, methods=["POST"]),
        Mount("/", app=mcp_app),
    ])
    return InternalMcpAuth(app)


def run() -> None:
    uvicorn.run(build_app(), host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8101")), log_level="info")


if __name__ == "__main__":
    run()
