"""Poetry Studio BFF: owns no Poetry facts and executes no agent run.

* Durable state lives behind the Java domain API (reached through the MCP control bridge).
* Run execution belongs to ``agent-worker``; this service creates the records and dispatches.
* Human-only writes (locators, source verification, per-item decisions) go straight to Java with a
  reviewer token that no agent-reachable process holds (A-contract D1).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from agent_bff import auth, precheck
from agent_bff import diff as diffing
from agent_bff.domain_control import DomainControlClient, DomainControlError, DomainControlRejected
from agent_bff.models import (
    APPLY_ROLES,
    ID_PATTERN,
    REVIEW_ROLES,
    SOURCE_REVIEW_ROLES,
    Actor,
    CreateTaskRequest,
    LocatorRequest,
    Proposal,
    ProposalItem,
    ProposalStatus,
    ReviewProposalRequest,
    Run,
    StartRunRequest,
    Task,
    TaskStatus,
    VerificationRequest,
)
from agent_bff.profile import ProfileError, profile_fingerprint
from agent_bff.studio_client import StudioClient, StudioError
from agent_bff.worker_client import WorkerClient, WorkerError

log = logging.getLogger("agent_bff")
API_PREFIX = "/api/poetry/v1/agent"
WORK_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,127}$"


# Path ids are forwarded verbatim into URLs on the domain-control bridge. They are always minted
# here as "<prefix>_<uuid4 hex>", so anything else is rejected at the route (422) instead of being
# allowed to carry "../" or "?" into another URL.
def _minted_id(prefix: str) -> Any:
    return Annotated[str, Path(pattern=rf"^{prefix}_[A-Za-z0-9_-]{{1,120}}$")]


TaskId = _minted_id("task")
RunId = _minted_id("run")
ProposalId = _minted_id("proposal")
WorkId = Annotated[str, Path(pattern=WORK_ID_PATTERN)]
EntityId = Annotated[str, Path(pattern=ID_PATTERN)]

TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED}
_ENUM_QUERY = r"^[A-Z][A-Z_]{0,31}$"

# Durable state lives behind the Java domain API; the BFF is stateless and can restart safely.
domain_control = DomainControlClient()
studio = StudioClient()
worker = WorkerClient()
app = FastAPI(title="Poetry Agent BFF", version="0.3.0")

app.add_middleware(auth.AuthMiddleware, api_prefix=API_PREFIX)
_origins = [o.strip() for o in os.getenv(
    "POETRY_STUDIO_ORIGINS", "http://localhost:5190,http://127.0.0.1:5190").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization", "Last-Event-ID"],
    max_age=600,
)


def error(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return body


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) and "code" in exc.detail else error("HTTP_ERROR", str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = []
    for item in exc.errors():
        message = str(item.get("msg", "invalid")).removeprefix("Value error, ")
        problems.append({"loc": [str(part) for part in item.get("loc", ())], "message": message})
    first = problems[0] if problems else {"loc": [], "message": "invalid request"}
    summary = f"{'.'.join(first['loc'])}: {first['message']}" if first["loc"] else first["message"]
    return JSONResponse(status_code=422, content={"error": error("VALIDATION_ERROR", summary, problems)})


def data(result: dict[str, Any]) -> dict[str, Any]:
    value = result.get("data")
    if not isinstance(value, dict):
        raise HTTPException(502, error("DOMAIN_RESPONSE_INVALID", "domain response did not contain an object data envelope"))
    return value


def page_of(result: dict[str, Any], convert: Any = None) -> dict[str, Any]:
    """Uniform ``{items, limit, offset, has_more}`` for every list endpoint."""
    value = result.get("data")
    if isinstance(value, list):
        value = {"items": value, "limit": len(value), "offset": 0, "has_more": False}
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise HTTPException(502, error("DOMAIN_RESPONSE_INVALID", "domain response did not contain a page"))
    items = [convert(item) for item in value["items"]] if convert else value["items"]
    return {"items": items, "limit": int(value.get("limit", len(items))), "offset": int(value.get("offset", 0)),
            "has_more": bool(value.get("has_more", False))}


def normalize_task(raw: dict[str, Any]) -> Task:
    return Task.model_validate({
        **{k: v for k, v in raw.items() if k not in {"requested_by", "requested_role"}},
        "actor": {"actor_id": raw["requested_by"], "role": raw["requested_role"]},
    })


def normalize_run(raw: dict[str, Any]) -> Run:
    return Run.model_validate(raw)


def _decode_proposal_json(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(raw["proposal_json"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(502, error("DOMAIN_RESPONSE_INVALID", "persisted proposal JSON is invalid")) from exc
    if not isinstance(payload, dict):
        raise HTTPException(502, error("DOMAIN_RESPONSE_INVALID", "persisted proposal JSON is not an object"))
    return payload


def normalize_proposal(raw: dict[str, Any], items: list[dict[str, Any]] | None = None) -> Proposal:
    payload = _decode_proposal_json(raw)
    review_status = raw.get("review_status")
    proposal_status = ProposalStatus.DRAFT
    application_state = "NOT_REQUESTED"
    if raw.get("status") == "APPLIED":
        proposal_status, application_state = ProposalStatus.APPLIED, "APPLIED"
    elif review_status == "APPROVED":
        proposal_status, application_state = ProposalStatus.APPROVED, "PENDING_DOMAIN_API"
    elif review_status == "REJECTED":
        proposal_status = ProposalStatus.REJECTED
    elif review_status == "PENDING":
        proposal_status = ProposalStatus.REVIEW_REQUIRED
    executable = diffing.executable_indexes(payload)
    approved: int | None = None
    if items is not None:
        decided = {int(item["item_index"]): item.get("decision") for item in items}
        # No item rows at all means the legacy rule applies on the Java side: every executable runs.
        approved = len(executable) if not decided else sum(1 for i in executable if decided.get(i) == "APPROVE")
    return Proposal.model_validate({
        "proposal_id": raw["proposal_id"], "task_id": raw.get("task_id", ""), "run_id": raw["run_id"],
        "mandate_id": raw["mandate_id"], "work_id": raw["work_id"], "status": proposal_status,
        "payload": payload, "created_at": raw["created_at"],
        "updated_at": raw.get("applied_at") or raw.get("reviewed_at") or raw["created_at"],
        "review_id": raw.get("review_id"), "reviewed_by": raw.get("reviewed_by"),
        "review_comment": raw.get("review_comment"), "application_state": application_state,
        "items": [ProposalItem.model_validate(item) for item in items] if items is not None else None,
        "executable_count": len(executable), "approved_executable_count": approved,
    })


def unavailable(exc: BaseException, code: str, what: str = "领域服务") -> HTTPException:
    """503 with fixed wording and a reference id. The exception text may name internal hosts or carry
    upstream response bodies, so it is logged, never returned (review item A-15)."""
    ref = uuid4().hex[:8]
    log.warning("%s ref=%s: %s", code, ref, str(exc)[:300])
    return HTTPException(503, error(code, f"{what}暂时不可用,请稍后重试。(参考编号 {ref})", {"ref": ref}))


def _fail(exc: DomainControlError, code: str, missing: str | None = None) -> HTTPException:
    reason = exc.reason if isinstance(exc, DomainControlRejected) else ""
    if missing and missing in reason:
        return HTTPException(404, error(code, f"{missing.removesuffix(' not found')}不存在。"))
    return unavailable(exc, code)


def fetch_task(task_id: str) -> Task:
    try:
        return normalize_task(data(domain_control.get_task(task_id)))
    except DomainControlError as exc:
        raise _fail(exc, "DOMAIN_TASK_UNAVAILABLE", "task not found") from exc


def fetch_run(run_id: str) -> Run:
    try:
        return normalize_run(data(domain_control.get_run(run_id)))
    except DomainControlError as exc:
        raise _fail(exc, "DOMAIN_RUN_UNAVAILABLE", "run not found") from exc


def fetch_items(proposal_id: str) -> list[dict[str, Any]] | None:
    """Per-item decisions; None when the endpoint is unavailable (e.g. V009 not yet applied)."""
    try:
        value = data(domain_control.proposal_items(proposal_id)).get("items")
    except (DomainControlError, HTTPException):
        return None
    return value if isinstance(value, list) else None


def fetch_proposal(proposal_id: str, *, with_items: bool = True) -> Proposal:
    try:
        raw = data(domain_control.get_proposal(proposal_id))
    except DomainControlError as exc:
        raise _fail(exc, "DOMAIN_PROPOSAL_UNAVAILABLE", "proposal not found") from exc
    return normalize_proposal(raw, fetch_items(proposal_id) if with_items else None)


def fetch_view(work_id: str) -> dict[str, Any]:
    try:
        return data(domain_control.work_studio_view(work_id))
    except DomainControlError as exc:
        raise _fail(exc, "DOMAIN_WORK_UNAVAILABLE", "work not found") from exc


def manifest() -> dict[str, Any]:
    if not os.getenv("POETRY_AGENT_PROFILE_ROOT", ""):
        log.error("POETRY_AGENT_PROFILE_ROOT is not configured")
        raise HTTPException(503, error("PROFILE_UNAVAILABLE", "智能体配置未就绪,请联系管理员。"))
    try:
        fingerprint = profile_fingerprint("authoring")
    except ProfileError as exc:
        raise unavailable(exc, "PROFILE_UNAVAILABLE", "智能体配置") from exc
    return {"profile_name": "authoring", "profile_fingerprint": fingerprint,
            "profile_manifest": {"fingerprint": fingerprint, "profile_root": "/profile", "governance": "read-propose-only"}}


def deerflow_enabled() -> bool:
    # Only selects the runtime *label*; the BFF never talks to the gateway (the worker does).
    return os.getenv("DEERFLOW_ENABLED", "false").lower() == "true"


def acting(request: Request, claimed: Actor | None) -> Actor:
    """The identity this request acts as.

    With authentication on, it is the signed-in account; a body ``actor`` that disagrees is rejected
    (the browser may not choose who it is). With ``POETRY_STUDIO_AUTH=off`` (offline demo only) the
    body actor is trusted, as before.
    """
    if auth.auth_mode() == "off":
        if claimed is None:
            raise HTTPException(422, error("ACTOR_REQUIRED", "actor is required while Studio authentication is off"))
        return claimed
    identity = getattr(request.state, "identity", None)
    if identity is None:  # the middleware guarantees this; fail closed if it ever does not
        raise HTTPException(401, error("AUTH_REQUIRED", "需要登录"), headers={"WWW-Authenticate": "Bearer"})
    if claimed is not None and (claimed.actor_id != identity.id or claimed.role != identity.role):
        raise HTTPException(403, error("ACTOR_MISMATCH", "请求中的身份与当前登录账号不一致"))
    return Actor(actor_id=identity.id, role=identity.role)


def settle_run(run_id: str, *, status: str | None, reason: str, event: tuple[str, dict[str, Any]] | None) -> list[str]:
    """Best-effort follow-up after a decision that Java has already committed.

    The content change is safe once Java says so; failing the whole request because a later bookkeeping
    write timed out would tell the editor "it failed" and leave the run unfinishable (review item A-10).
    Returns warning codes instead of raising.
    """
    warnings: list[str] = []
    if status is not None:
        try:
            domain_control.change_run_state(run_id, {"status": status, "reason": reason})
        except DomainControlError as exc:
            log.warning("RUN_STATE_NOT_UPDATED run=%s: %s", run_id, str(exc)[:200])
            warnings.append("RUN_STATE_NOT_UPDATED")
    if event is not None:
        try:
            domain_control.append_event(run_id, {"event_type": event[0], "payload": event[1]})
        except DomainControlError as exc:
            log.warning("EVENT_NOT_RECORDED run=%s: %s", run_id, str(exc)[:200])
            warnings.append("EVENT_NOT_RECORDED")
    return warnings


def reconcile_decided(proposal: Proposal) -> list[str] | None:
    """Repair a run left non-terminal after its proposal was already decided/applied.

    Returns warnings when it repaired something (or found nothing to repair), None when the proposal is
    not in a decided state at all. Idempotent.
    """
    nothing_left = (
        proposal.status == ProposalStatus.APPLIED
        or proposal.status == ProposalStatus.REJECTED
        or (proposal.status == ProposalStatus.APPROVED and proposal.approved_executable_count == 0)
    )
    if not nothing_left:
        return None
    try:
        run = fetch_run(proposal.run_id)
    except HTTPException:
        return ["RUN_STATE_NOT_UPDATED"]
    if run.status in TERMINAL:
        return []
    warnings = settle_run(
        proposal.run_id, status="COMPLETED", reason="决定已生效;运行状态已按提案结果补记。",
        event=("RUN_RECONCILED", {"proposal_id": proposal.proposal_id, "proposal_status": str(proposal.status)}))
    return warnings or ["RECONCILED"]


def pending_work(proposal: Proposal) -> bool:
    """True while a human still has something to do with this proposal."""
    if proposal.status == ProposalStatus.REVIEW_REQUIRED:
        return True
    if proposal.status == ProposalStatus.APPROVED:
        # Unknown (items unreadable) counts as pending: settling an approved-but-unapplied proposal would be wrong.
        return proposal.approved_executable_count is None or proposal.approved_executable_count > 0
    return False


def task_is_blocked_by_review(task: Task) -> bool:
    """AWAITING_REVIEW normally blocks a new run. When every proposal of the task is already settled the
    status is stale (a write-back failed earlier): repair it and let the editor continue."""
    try:
        rows = page_of(domain_control.list_proposals(task_id=task.task_id, limit=50, offset=0))["items"]
        proposals = [normalize_proposal(raw, fetch_items(raw["proposal_id"])) for raw in rows]
    except (DomainControlError, HTTPException, KeyError, ValueError):
        return True
    if not proposals or any(pending_work(item) for item in proposals):
        return True
    for item in proposals:
        reconcile_decided(item)
    return False


def _rejected(exc: DomainControlRejected, code: str) -> HTTPException:
    """Java refused the request for a reason the editor can act on: 409 for a state conflict, else 422."""
    return HTTPException(409 if exc.status_code == 409 else 422, error(code, exc.reason))


def _studio_error(exc: StudioError) -> HTTPException:
    return HTTPException(exc.status_code, error(exc.code, str(exc), exc.details))


# ----------------------------------------------------------------------------------------- auth

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=1, max_length=256)


def _client_ip(request: Request) -> str:
    """The caller's address. Behind exactly one trusted reverse proxy (POETRY_STUDIO_TRUST_PROXY=1) the real
    client is the LAST X-Forwarded-For entry (that hop is appended by the proxy; earlier ones are caller-controlled)."""
    if os.getenv("POETRY_STUDIO_TRUST_PROXY", "").strip() == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        last = forwarded.split(",")[-1].strip() if forwarded else ""
        if last:
            return last[:64]
    return request.client.host if request.client else "unknown"


@app.post(f"{API_PREFIX}/auth/login")
def login(request: Request, body: LoginRequest) -> dict[str, Any]:
    if auth.auth_mode() == "off":
        raise HTTPException(409, error("AUTH_DISABLED", "Studio 登录当前关闭(POETRY_STUDIO_AUTH=off,仅离线演示)"))
    if not auth.configured():
        raise HTTPException(503, error("AUTH_NOT_CONFIGURED", "未配置账号文件或会话密钥(POETRY_STUDIO_USERS_FILE / POETRY_STUDIO_SESSION_SECRET)"))
    ip = _client_ip(request)
    key = f"{body.user_id.lower()}@{ip}"
    wait = max(auth.limiter.blocked_for(key), auth.ip_limiter.blocked_for(ip))
    if wait:
        raise HTTPException(429, error("LOGIN_LOCKED", f"尝试次数过多,请 {wait} 秒后再试"), headers={"Retry-After": str(wait)})
    user = auth.users.get(body.user_id)
    # Always run one scrypt, so an unknown account takes as long as a wrong password.
    valid = auth.verify_password(body.password, user.password_hash if user else auth.dummy_hash())
    if user is None or not valid:
        auth.limiter.fail(key)
        auth.ip_limiter.fail(ip)
        auth.log.warning("Studio login failed for an account (id length %d)", len(body.user_id))
        raise HTTPException(401, error("LOGIN_FAILED", "账号或密码不正确"))
    auth.limiter.succeed(key)
    token, expires = auth.issue_session(user)
    return {"token": token, "expires_at": expires, "actor": {"actor_id": user.id, "role": user.role, "name": user.name}}


@app.get(f"{API_PREFIX}/auth/me")
def whoami(request: Request) -> dict[str, Any]:
    if auth.auth_mode() == "off":
        return {"auth_mode": "off", "actor": None,
                "warning": "登录未启用:身份由请求自己声明,只能用于离线演示。"}
    identity = request.state.identity  # guaranteed by the middleware
    return {"auth_mode": "required", "actor": {"actor_id": identity.id, "role": identity.role, "name": identity.name},
            "expires_at": identity.expires_at}


@app.post(f"{API_PREFIX}/auth/events-ticket/{{run_id}}")
def events_ticket(request: Request, run_id: RunId) -> dict[str, Any]:
    """EventSource cannot send an Authorization header: hand it a 60-second ticket for this run only."""
    if auth.auth_mode() == "off":
        return {"ticket": "", "expires_at": 0}
    ticket, expires = auth.issue_ticket(request.state.identity, run_id)
    return {"ticket": ticket, "expires_at": expires}


# --------------------------------------------------------------------------------------- health

@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "agent-bff"}


@app.get("/health/ready")
def ready() -> dict[str, Any]:
    return {
        "status": "ready" if domain_control.configured() else "not_ready",
        "service": "agent-bff",
        "persistence": "JAVA_DOMAIN_API",
        "domain_control_configured": domain_control.configured(),
        "worker_configured": worker.configured(),
        "reviewer_token_configured": studio.configured(),
        "deerflow_enabled": deerflow_enabled(),
        "auth_mode": auth.auth_mode(),
        "auth_configured": auth.configured(),
    }


# ---------------------------------------------------------------------------------------- tasks

@app.get(f"{API_PREFIX}/tasks")
def list_tasks(
    work_id: Annotated[str | None, Query(pattern=WORK_ID_PATTERN)] = None,
    task_status: Annotated[str | None, Query(alias="status", pattern=_ENUM_QUERY)] = None,
    task_type: Annotated[str | None, Query(pattern=_ENUM_QUERY)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> dict[str, Any]:
    try:
        result = domain_control.list_tasks(work_id=work_id, status=task_status, task_type=task_type, limit=limit, offset=offset)
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_TASK_LIST_UNAVAILABLE") from exc
    return page_of(result, lambda raw: normalize_task(raw).model_dump(mode="json"))


@app.post(f"{API_PREFIX}/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(request: Request, body: CreateTaskRequest) -> Task:
    who = acting(request, body.actor)
    task_id = f"task_{uuid4().hex}"
    try:
        result = domain_control.create_task({
            "task_id": task_id, "work_id": body.work_id, "title": body.title, "task_type": body.task_type,
            "requested_by": who.actor_id, "requested_role": who.role,
            "instructions": body.instructions, "requested_profile": body.requested_profile})
    except DomainControlError as exc:
        if "work not found" in str(exc):
            raise HTTPException(404, error("WORK_NOT_FOUND", f"work {body.work_id} does not exist in the domain base")) from exc
        raise unavailable(exc, "DOMAIN_TASK_CREATE_UNAVAILABLE") from exc
    return normalize_task(data(result))


@app.get(f"{API_PREFIX}/tasks/{{task_id}}", response_model=Task)
def get_task(task_id: TaskId) -> Task:
    return fetch_task(task_id)


@app.get(f"{API_PREFIX}/tasks/{{task_id}}/runs")
def task_runs(task_id: TaskId) -> dict[str, Any]:
    fetch_task(task_id)
    try:
        result = domain_control.task_runs(task_id)
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_RUN_LIST_UNAVAILABLE") from exc
    return page_of(result, lambda raw: normalize_run(raw).model_dump(mode="json"))


@app.post(f"{API_PREFIX}/tasks/{{task_id}}/run", response_model=Run, status_code=status.HTTP_202_ACCEPTED)
def start_run(task_id: TaskId, body: StartRunRequest | None = None) -> Run:
    task = fetch_task(task_id)
    if task.status == TaskStatus.RUNNING:
        raise HTTPException(409, error("RUN_ALREADY_ACTIVE", "task already has an active run", {"run_id": task.active_run_id}))
    if task.status == TaskStatus.AWAITING_REVIEW and task_is_blocked_by_review(task):
        raise HTTPException(409, error("TASK_NOT_RUNNABLE", "有提案正等待人工评审或应用,请先处理。"))
    run_id, mandate_id = f"run_{uuid4().hex}", f"mandate_{uuid4().hex}"
    profile = manifest()
    wants_stub = body is not None and body.runtime == "STUB"
    runtime = "DEERFLOW" if deerflow_enabled() and not wants_stub else "STUB"
    try:
        domain_control.create_run(task_id, {"run_id": run_id, "mandate_id": mandate_id, "runtime": runtime, **profile})
    except DomainControlRejected as exc:
        if exc.status_code == 409:  # Java's atomic claim lost the race: another run owns this task
            raise HTTPException(409, error("RUN_ALREADY_ACTIVE", "该任务已有进行中的运行。")) from exc
        raise _rejected(exc, "RUN_REJECTED") from exc
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_RUN_CREATE_UNAVAILABLE") from exc
    try:
        # Admit as RUNNING *before* dispatch: the deterministic runtime can finish in milliseconds and
        # a later admission would overwrite its AWAITING_REVIEW state.
        domain_control.admit_run(run_id, {"status": "RUNNING"})
    except DomainControlError as exc:
        settle_run(run_id, status="FAILED", reason="运行登记未完成,已放弃。", event=None)
        raise unavailable(exc, "DOMAIN_RUN_ADMISSION_UNAVAILABLE") from exc
    dispatch = {
        "run_id": run_id, "task_id": task_id, "mandate_id": mandate_id, "work_id": task.work_id,
        "task_type": task.task_type, "instructions": task.instructions, "runtime": runtime,
        "profile_fingerprint": profile["profile_fingerprint"], "actor_role": task.actor.role,
    }
    try:
        worker.dispatch(dispatch)
    except WorkerError as exc:
        log.warning("WORKER_UNAVAILABLE run=%s: %s", run_id, str(exc)[:300])
        reason = "运行器暂时不可用,本次运行未开始。"
        try:
            domain_control.admit_run(run_id, {"status": "FAILED", "reason": reason})
            domain_control.append_event(run_id, {"event_type": "RUNTIME_FAILED", "payload": {"reason": "worker_unavailable"}})
        except DomainControlError:
            pass
        raise HTTPException(503, error("WORKER_UNAVAILABLE", reason, {"run_id": run_id})) from exc
    return fetch_run(run_id)


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: Actor | None = None


@app.post(f"{API_PREFIX}/runs/{{run_id}}/cancel", response_model=Run)
def cancel_run(request: Request, run_id: RunId, body: CancelRunRequest | None = None) -> Run:
    who = acting(request, body.actor if body else None) if auth.auth_mode() == "required" or (body and body.actor) else None
    run = fetch_run(run_id)
    if run.status in TERMINAL:
        return run  # idempotent
    if who is not None and auth.auth_mode() == "required" and who.role != "PLATFORM_ADMIN":
        owner = fetch_task(run.task_id).actor.actor_id
        if owner != who.actor_id:
            raise HTTPException(403, error("CANCEL_NOT_ALLOWED", "只有发起该任务的人或平台管理员可以取消运行。"))
    notified = True
    try:
        worker.cancel(run_id)
    except WorkerError:
        notified = False
    cancelled_by = who.actor_id if who else None
    try:
        domain_control.change_run_state(run_id, {"status": "FAILED", "reason": "已由编辑取消"})
        if not notified:
            domain_control.append_event(run_id, {"event_type": "RUN_CANCELLED", "payload": {"worker_notified": False, "by": cancelled_by}})
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_RUN_CANCEL_UNAVAILABLE") from exc
    return fetch_run(run_id)


def latest_budget(run_id: str) -> tuple[dict[str, Any] | None, str | None]:
    after, latest, latest_id = 0, None, None
    for _ in range(40):
        rows = domain_control.events(run_id, after).get("data", [])
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            after = max(after, int(row["event_id"]))
            if row.get("event_type") == "BUDGET_UPDATE":
                try:
                    parsed = json.loads(row.get("payload_json") or "{}")
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    latest, latest_id = parsed, str(row["event_id"])
        if len(rows) < 250:
            break
    return latest, latest_id


@app.get(f"{API_PREFIX}/runs/{{run_id}}", response_model=Run)
def get_run(run_id: RunId) -> Run:
    run = fetch_run(run_id)
    try:
        budget, _ = latest_budget(run_id)
    except (DomainControlError, ValueError, KeyError, TypeError):
        budget = None
    return run.model_copy(update={"budget": budget}) if budget else run


@app.get(f"{API_PREFIX}/runs/{{run_id}}/budget")
def run_budget(run_id: RunId) -> dict[str, Any]:
    fetch_run(run_id)
    try:
        budget, event_id = latest_budget(run_id)
    except (DomainControlError, ValueError, KeyError, TypeError) as exc:
        raise unavailable(exc, "DOMAIN_EVENT_STREAM_UNAVAILABLE") from exc
    return {"run_id": run_id, "budget": budget, "event_id": event_id}


class StreamGate:
    """Caps concurrent SSE connections (each one polls the bridge). The slot is released exactly once,
    by the generator's finally or, if the generator never started, by the response's background task."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.open = 0

    @staticmethod
    def limit() -> int:
        try:
            return max(1, int(os.getenv("POETRY_STUDIO_MAX_EVENT_STREAMS", "20")))
        except ValueError:
            return 20

    def acquire(self) -> bool:
        with self._lock:
            if self.open >= self.limit():
                return False
            self.open += 1
            return True

    def release_once(self, released: list[bool]) -> None:
        with self._lock:
            if not released[0]:
                released[0] = True
                self.open = max(0, self.open - 1)


stream_gate = StreamGate()


@app.get(f"{API_PREFIX}/runs/{{run_id}}/events")
async def run_events(
    run_id: RunId,
    last_event_id: Annotated[str | None, Header()] = None,
    after_event_id: Annotated[str | None, Query(pattern=r"^[0-9]{1,18}$")] = None,
) -> EventSourceResponse:
    await asyncio.to_thread(fetch_run, run_id)
    if not stream_gate.acquire():
        raise HTTPException(429, error("TOO_MANY_EVENT_STREAMS", "事件连接过多,请关闭不用的页面后重试。"))
    released = [False]
    cursor = after_event_id if after_event_id is not None else last_event_id
    start = int(cursor) if cursor and cursor.isascii() and cursor.isdigit() else 0

    async def stream() -> AsyncIterator[dict[str, str]]:
        after, idle = start, 0
        try:
            async for item in poll(after, idle):
                yield item
        finally:
            stream_gate.release_once(released)

    async def poll(after: int, idle: int) -> AsyncIterator[dict[str, str]]:
        while True:
            try:
                result = await asyncio.to_thread(domain_control.events, run_id, after)
                rows = result.get("data", [])
                if not isinstance(rows, list):
                    yield {"event": "error", "data": json.dumps(error("DOMAIN_RESPONSE_INVALID", "event stream payload is invalid"))}
                    return
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    after = max(after, int(row["event_id"]))
                    payload = json.loads(row.get("payload_json") or "{}")
                    yield {"event": row["event_type"], "id": str(row["event_id"]), "data": json.dumps({
                        "event_id": str(row["event_id"]), "run_id": row["run_id"], "event_type": row["event_type"],
                        "occurred_at": row["occurred_at"], "payload": payload})}
                idle = 0 if rows else idle + 1
            except (DomainControlError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                ref = uuid4().hex[:8]
                log.warning("DOMAIN_EVENT_STREAM_UNAVAILABLE ref=%s: %s", ref, str(exc)[:300])
                yield {"event": "error", "data": json.dumps(error(
                    "DOMAIN_EVENT_STREAM_UNAVAILABLE", f"事件流暂时不可用。(参考编号 {ref})", {"ref": ref}))}
                return
            # The connection stays open for as long as the client does; back off while nothing happens.
            await asyncio.sleep(min(1.0 + idle * 0.5, 5.0))

    return EventSourceResponse(stream(), ping=15, background=BackgroundTask(stream_gate.release_once, released))


# ------------------------------------------------------------------------------------ proposals

@app.get(f"{API_PREFIX}/proposals")
def list_proposals(
    work_id: Annotated[str | None, Query(pattern=WORK_ID_PATTERN)] = None,
    proposal_status: Annotated[str | None, Query(alias="status", pattern=_ENUM_QUERY)] = None,
    run_id: Annotated[str | None, Query(pattern=r"^run_[A-Za-z0-9_-]{1,120}$")] = None,
    task_id: Annotated[str | None, Query(pattern=r"^task_[A-Za-z0-9_-]{1,120}$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> dict[str, Any]:
    # The public status vocabulary is the BFF's (REVIEW_REQUIRED, APPROVED, …); map it onto Java columns.
    java_filters: dict[str, str | None] = {"status": None, "review_status": None}
    if proposal_status == "REVIEW_REQUIRED":
        java_filters["review_status"] = "PENDING"
    elif proposal_status in {"APPROVED", "REJECTED"}:
        java_filters["review_status"] = proposal_status
    elif proposal_status == "APPLIED":
        java_filters["status"] = "APPLIED"
    elif proposal_status is not None:
        raise HTTPException(422, error("VALIDATION_ERROR", f"status: unsupported proposal status {proposal_status}"))
    try:
        result = domain_control.list_proposals(work_id=work_id, run_id=run_id, task_id=task_id, limit=limit, offset=offset, **java_filters)
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_PROPOSAL_LIST_UNAVAILABLE") from exc
    return page_of(result, lambda raw: normalize_proposal(raw).model_dump(mode="json"))


@app.get(f"{API_PREFIX}/proposals/{{proposal_id}}", response_model=Proposal)
def get_proposal(proposal_id: ProposalId) -> Proposal:
    return fetch_proposal(proposal_id)


@app.get(f"{API_PREFIX}/proposals/{{proposal_id}}/diff")
def proposal_diff(proposal_id: ProposalId) -> dict[str, Any]:
    proposal = fetch_proposal(proposal_id)
    try:
        view: dict[str, Any] | None = fetch_view(proposal.work_id)
    except HTTPException:
        view = None
    raw_items = [item.model_dump(mode="json") for item in proposal.items or []]
    return diffing.build_diff(proposal.model_dump(mode="json"), view, raw_items)


@app.post(f"{API_PREFIX}/proposals/{{proposal_id}}/review", response_model=Proposal)
def review_proposal(request: Request, proposal_id: ProposalId, body: ReviewProposalRequest) -> Proposal:
    who = acting(request, body.actor)
    if who.role not in REVIEW_ROLES:
        raise HTTPException(403, error("REVIEW_ROLE_REQUIRED", "only editorial reviewers may review a proposal"))
    proposal = fetch_proposal(proposal_id)
    if proposal.status != ProposalStatus.REVIEW_REQUIRED:
        repaired = reconcile_decided(proposal)  # a retry after a half-finished earlier decision
        if repaired:
            return proposal.model_copy(update={"warnings": repaired})
        raise HTTPException(409, error("PROPOSAL_NOT_REVIEWABLE", f"提案当前状态为 {proposal.status},不能再评审。"))
    changes = proposal.payload.get("changes") or []
    executable = diffing.executable_indexes(proposal.payload)
    decisions = body.item_decisions or []
    given = {item.item_index for item in decisions}
    out_of_range = sorted(i for i in given if i >= len(changes))
    if out_of_range:
        raise HTTPException(422, error("ITEM_DECISION_INDEX_INVALID", "item_decisions refer to changes that do not exist", {"item_index": out_of_range}))
    if body.decision == "APPROVE" and executable:
        missing = sorted(set(executable) - given)
        if missing:
            raise HTTPException(422, error(
                "ITEM_DECISIONS_REQUIRED", "every executable change needs an explicit APPROVE or REJECT before the proposal can be approved",
                {"missing_item_index": missing}))
    if decisions:
        try:
            studio.put_items(proposal_id, {
                "decisions": [{"item_index": d.item_index, "decision": d.decision, **({"comment": d.comment} if d.comment else {})} for d in decisions],
                "reviewer": who.actor_id, "reviewer_role": who.role})
        except StudioError as exc:
            raise _studio_error(exc) from exc
    review_id = f"review_{uuid4().hex}"
    approved_executable = sum(1 for d in decisions if d.decision == "APPROVE" and d.item_index in executable)
    try:
        domain_control.record_review(
            proposal_id=proposal_id, work_id=proposal.work_id, run_id=proposal.run_id, mandate_id=proposal.mandate_id,
            actor_role=who.role, review_id=review_id, reviewer_id=who.actor_id,
            decision=body.decision, comment=body.comment)
    except DomainControlRejected as exc:
        raise _rejected(exc, "REVIEW_REJECTED") from exc
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_REVIEW_UNAVAILABLE") from exc
    # The decision is committed. Everything below is bookkeeping: report problems, do not fail the request.
    event = ("PROPOSAL_APPROVED" if body.decision == "APPROVE" else "PROPOSAL_REJECTED",
             {"proposal_id": proposal_id, "review_id": review_id, "executable": len(executable),
              "approved_executable": approved_executable})
    if body.decision == "REJECT":
        warnings = settle_run(proposal.run_id, status="COMPLETED", reason="人工评审驳回了该草稿提案。", event=event)
    elif not executable or approved_executable == 0:
        # Nothing can be applied (e.g. a gap report): approval keeps it as an editorial record.
        warnings = settle_run(proposal.run_id, status="COMPLETED", reason="已批准;没有可应用的可执行项,提案作为编辑记录留存。", event=event)
    else:
        warnings = settle_run(proposal.run_id, status=None, reason="", event=event)
    result = fetch_proposal(proposal_id)
    return result.model_copy(update={"warnings": warnings}) if warnings else result


class ApplyProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: Actor | None = None


@app.post(f"{API_PREFIX}/proposals/{{proposal_id}}/apply", response_model=Proposal)
def apply_proposal(request: Request, proposal_id: ProposalId, body: ApplyProposalRequest | None = None) -> Proposal:
    who = acting(request, body.actor if body else None)
    if who.role not in APPLY_ROLES:
        raise HTTPException(403, error("APPLY_ROLE_REQUIRED", "this role may not apply an approved proposal"))
    proposal = fetch_proposal(proposal_id)
    if proposal.status == ProposalStatus.APPLIED:
        # Java already applied it. If the follow-up write failed last time, finish it now (idempotent).
        repaired = reconcile_decided(proposal)
        if repaired:  # [] means the run was already finished: a plain double-apply, which stays a 409 below
            return proposal.model_copy(update={"warnings": repaired})
    if proposal.status != ProposalStatus.APPROVED or proposal.application_state != "PENDING_DOMAIN_API" or proposal.review_id is None:
        raise HTTPException(409, error("PROPOSAL_NOT_APPLICABLE", f"提案当前状态为 {proposal.status},不能应用。"))
    if proposal.items is None and (proposal.executable_count or 0) > 0:
        raise HTTPException(503, error("ITEMS_UNAVAILABLE", "per-item decisions cannot be read; refusing to apply blindly"))
    if not proposal.approved_executable_count:
        raise HTTPException(409, error("NOTHING_TO_APPLY", "no executable change was approved; the proposal stays as an editorial record"))
    try:
        domain_control.apply_proposal(
            proposal_id=proposal.proposal_id, work_id=proposal.work_id, run_id=proposal.run_id,
            mandate_id=proposal.mandate_id, review_id=proposal.review_id)
    except DomainControlRejected as exc:
        raise _rejected(exc, "APPLY_REJECTED") from exc
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_APPLY_UNAVAILABLE") from exc
    # Java committed the DRAFT rows. A failure past this point must not look like a failed application.
    warnings = settle_run(
        proposal.run_id, status="COMPLETED", reason="已批准的草稿操作已由领域服务写入。",
        event=("DRAFT_APPLICATION_COMPLETED",
               {"proposal_id": proposal.proposal_id, "review_id": proposal.review_id, "by": who.actor_id}))
    result = fetch_proposal(proposal_id)
    return result.model_copy(update={"warnings": warnings}) if warnings else result


# ----------------------------------------------------------------------------------------- works

@app.get(f"{API_PREFIX}/works")
def list_works(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> dict[str, Any]:
    try:
        return page_of(domain_control.list_works(limit=limit, offset=offset))
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_WORK_LIST_UNAVAILABLE") from exc


@app.get(f"{API_PREFIX}/works/{{work_id}}/overview")
def work_overview(work_id: WorkId) -> dict[str, Any]:
    return fetch_view(work_id)


@app.get(f"{API_PREFIX}/works/{{work_id}}/coverage")
def work_coverage(work_id: WorkId) -> dict[str, Any]:
    try:
        return data(domain_control.work_coverage(work_id))
    except DomainControlError as exc:
        raise _fail(exc, "DOMAIN_COVERAGE_UNAVAILABLE", "work not found") from exc


@app.get(f"{API_PREFIX}/works/{{work_id}}/gap-report")
def work_gap_report(work_id: WorkId) -> dict[str, Any]:
    report = fetch_view(work_id).get("gap_report")
    if not isinstance(report, dict):
        raise HTTPException(502, error("DOMAIN_RESPONSE_INVALID", "studio view did not include a gap report"))
    return report


@app.get(f"{API_PREFIX}/works/{{work_id}}/precheck")
def work_precheck(work_id: WorkId) -> dict[str, Any]:
    return precheck.run_precheck(work_id, fetch_view(work_id), precheck.load_bundle())


# --------------------------------------------------------------------------------------- sources

@app.get(f"{API_PREFIX}/sources")
def list_sources(
    verification_status: Annotated[str | None, Query(pattern=_ENUM_QUERY)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> dict[str, Any]:
    try:
        return page_of(domain_control.list_sources(verification_status=verification_status, limit=limit, offset=offset))
    except DomainControlError as exc:
        raise unavailable(exc, "DOMAIN_SOURCE_LIST_UNAVAILABLE") from exc


def _require_source_reviewer(actor: Actor) -> None:
    if actor.role not in SOURCE_REVIEW_ROLES:
        raise HTTPException(403, error(
            "SOURCE_REVIEW_ROLE_REQUIRED", "only a historical reviewer or platform admin may enter locators or verify sources; an agent never can"))


@app.put(f"{API_PREFIX}/sources/citations/{{claim_id}}/{{source_id}}/locator")
def put_locator(request: Request, claim_id: EntityId, source_id: EntityId, body: LocatorRequest) -> dict[str, Any]:
    who = acting(request, body.actor)
    _require_source_reviewer(who)
    if not precheck.is_real_locator(body.locator):
        raise HTTPException(422, error("LOCATOR_PLACEHOLDER", "locator must be a real, re-checkable position (not empty or a placeholder such as 待核查)"))
    payload: dict[str, Any] = {"locator": body.locator.strip(), "reviewer": who.actor_id, "reviewer_role": who.role}
    if body.evidence_excerpt:
        payload["evidence_excerpt"] = body.evidence_excerpt
    if body.note:
        payload["note"] = body.note
    try:
        return studio.put_locator(claim_id, source_id, payload)
    except StudioError as exc:
        raise _studio_error(exc) from exc


@app.post(f"{API_PREFIX}/sources/{{source_id}}/verification")
def verify_source(request: Request, source_id: EntityId, body: VerificationRequest) -> dict[str, Any]:
    who = acting(request, body.actor)
    _require_source_reviewer(who)
    payload: dict[str, Any] = {"decision": body.decision, "reviewer": who.actor_id, "reviewer_role": who.role}
    if body.note:
        payload["note"] = body.note
    try:
        return studio.verify_source(source_id, payload)
    except StudioError as exc:
        raise _studio_error(exc) from exc


def run() -> None:
    uvicorn.run("agent_bff.main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8100")), reload=False)


if __name__ == "__main__":
    run()
