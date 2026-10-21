"""Admin / internal debug routes."""

from __future__ import annotations

import json
from typing import Annotated, Any

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from jc.api.deps import (
    get_admin_user_service,
    get_db,
    get_feedback_service,
    get_session_audit_service,
    require_admin,
)
from jc.diagnostics.harness_inventory import build_harness_inventory
from jc.exceptions import NotFoundError
from jc.schemas.admin_feedback import (
    AdminFeedbackReplyRequest,
    AdminFeedbackStatusRequest,
    AdminFeedbackThreadDetailResponse,
    AdminFeedbackThreadListResponse,
)
from jc.schemas.admin_llm import (
    AdminLlmAttempt,
    AdminLlmCallDetailResponse,
    AdminLlmCallItem,
    AdminLlmCallListResponse,
    AdminLlmUsageResponse,
    AdminLlmUsageRow,
)
from jc.schemas.admin_session import (
    AdminCheckpointResponse,
    AdminInventoryResponse,
    AdminMessageListResponse,
    AdminSessionDetailResponse,
    AdminSessionListResponse,
    AdminTimelineResponse,
    AdminTraceListResponse,
)
from jc.schemas.admin_user import AdminUserDetailResponse, AdminUserListResponse
from jc.schemas.profile import ProfileResponse
from jc.services.admin_user_service import AdminUserService
from jc.services.feedback_service import FeedbackService
from jc.services.session_audit_service import SessionAuditService
from jc.stores.agent_store import SESSION_SORT
from jc.stores.agent_trace_store import AgentTraceStore
from jc.stores.feedback_store import FEEDBACK_SORT
from jc.stores.llm_call_store import LLM_CALL_SORT, LlmCallStore
from jc.stores.user_store import USER_SORT, UserStore

router = APIRouter(prefix="/admin", tags=["admin"])


def _SortBy(spec) -> Any:  # noqa: ANN001, N802
    """The `sort_by` parameter type for a list whose order comes from `spec`.

    `Annotated[...]` rather than `sort_by: str | None = Query(default=None)` so
    the function's runtime default is a real `None`: these handlers are also
    called directly from tests, where a `Query` object left as the default value
    would reach the store as the requested sort field.

    The description is generated from the store's own `SortSpec`, so the schema
    cannot drift from what the query actually accepts and an operator sees the
    supported fields instead of discovering them by collecting 400s.
    """
    return Annotated[
        str | None,
        Query(description=f"排序字段，可选：{', '.join(spec.keys)}"),
    ]


#: Shared across the four lists: the direction vocabulary is not per-table. The
#: pattern rejects anything else at the edge, before it reaches `SortSpec`.
_SortDir = Annotated[
    str | None,
    Query(pattern="^(asc|desc)$", description="asc 或 desc，默认按该列表的默认方向"),
]

#: Paging bounds are shared by every admin list. `Annotated` for the same reason
#: as `_SortBy`: the runtime default must be the value itself, not a `Query`.
_Limit = Annotated[int, Query(ge=1, le=200)]
_Offset = Annotated[int, Query(ge=0)]

_SessionSortBy = _SortBy(SESSION_SORT)
_UserSortBy = _SortBy(USER_SORT)
_LlmSortBy = _SortBy(LLM_CALL_SORT)
_FeedbackSortBy = _SortBy(FEEDBACK_SORT)


@router.get(
    "/sessions",
    response_model=AdminSessionListResponse,
    summary="列出全部 Agent 会话（不限用户）",
)
async def admin_list_sessions(
    limit: _Limit = 50,
    offset: _Offset = 0,
    user_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(description="按 session id、thread id 或用户邮箱模糊匹配")] = None,
    sort_by: _SessionSortBy = None,
    sort_dir: _SortDir = None,
    _: UserActor = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminSessionListResponse:
    return await audit.list_sessions(
        limit=limit,
        offset=offset,
        user_id=user_id,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=AdminSessionDetailResponse,
    summary="会话详情",
)
async def admin_get_session(
    session_id: str,
    _: UserActor = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminSessionDetailResponse:
    return await audit.get_session(session_id)


@router.get(
    "/sessions/{session_id}/timeline",
    response_model=AdminTimelineResponse,
    summary="按 turn 聚合的 SSE 审计时间线",
)
async def admin_session_timeline(
    session_id: str,
    limit: int = Query(default=2000, ge=1, le=5000),
    _: UserActor = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminTimelineResponse:
    return await audit.get_timeline(session_id, limit=limit)


@router.get(
    "/sessions/{session_id}/checkpoint",
    response_model=AdminCheckpointResponse,
    summary="LangGraph checkpoint 完整消息（含 system prompt）",
)
async def admin_session_checkpoint(
    session_id: str,
    _: UserActor = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminCheckpointResponse:
    return await audit.get_checkpoint(session_id)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=AdminMessageListResponse,
    summary="该会话的 UI 投影消息列表（jc_agent_message）",
)
async def admin_session_messages(
    session_id: str,
    limit: int = Query(default=500, ge=1, le=2000),
    _: UserActor = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminMessageListResponse:
    return await audit.list_messages(session_id, limit=limit)


@router.get(
    "/sessions/{session_id}/trace",
    response_model=AdminTraceListResponse,
    summary="该会话的完整事件账本（jc_agent_trace，与 trace.jsonl 同源，供页面内查看）",
)
async def admin_session_trace(
    session_id: str,
    limit: int = Query(default=5000, ge=1, le=5000),
    _: UserActor = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminTraceListResponse:
    return await audit.list_trace(session_id, limit=limit)


@router.get(
    "/inventory",
    response_model=AdminInventoryResponse,
    summary="MCP / Tool / Skill / Middleware 清单",
)
async def admin_harness_inventory(
    _: UserActor = Depends(require_admin),
) -> AdminInventoryResponse:
    return build_harness_inventory()


@router.get(
    "/llm/calls",
    response_model=AdminLlmCallListResponse,
    summary="LLM 调用审计日志（可按用户 / 档案 / 分类 / 状态筛选）",
)
async def admin_list_llm_calls(
    limit: _Limit = 50,
    offset: _Offset = 0,
    user_id: Annotated[str | None, Query()] = None,
    profile_id: Annotated[str | None, Query()] = None,
    scenario: Annotated[str | None, Query()] = None,
    caller: Annotated[str | None, Query()] = None,
    channel: Annotated[str | None, Query(description="router 或 harness")] = None,
    status: Annotated[str | None, Query(description="success 或 failed")] = None,
    trace_id: Annotated[str | None, Query()] = None,
    sort_by: _LlmSortBy = None,
    sort_dir: _SortDir = None,
    _: UserActor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminLlmCallListResponse:
    rows, total, sorted_by, sorted_dir = await LlmCallStore(db).list_calls(
        limit=limit,
        offset=offset,
        user_id=user_id,
        profile_id=profile_id,
        scenario=scenario,
        caller=caller,
        channel=channel,
        status=status,
        trace_id=trace_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    calls = [AdminLlmCallItem.model_validate(row, from_attributes=True) for row in rows]
    # Annotate with the owning user in one batched query (same contract as the session
    # audit list). Resolved here rather than denormalised onto `jc_llm_call` so renaming
    # a user does not leave stale names in the audit log.
    users = await UserStore(db).get_by_ids([c.user_id for c in calls if c.user_id])
    for call in calls:
        user = users.get(call.user_id) if call.user_id else None
        if user is not None:
            call.user_display_name = user.meta.display_name if user.meta else None
            call.user_email = user.email
    return AdminLlmCallListResponse(
        calls=calls,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=sorted_by,
        sort_dir=sorted_dir,
    )


@router.get(
    "/llm/calls/{call_id}",
    response_model=AdminLlmCallDetailResponse,
    summary="单次 LLM 调用详情（含每个 endpoint 的尝试记录）",
)
async def admin_get_llm_call(
    call_id: str,
    include_payload: bool = Query(
        default=False,
        description="是否返回 prompt / 响应 / 思考原文。其中含简历个人信息，默认不返回。",
    ),
    _: UserActor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminLlmCallDetailResponse:
    store = LlmCallStore(db)
    row = await store.get_call(call_id)
    if row is None:
        raise NotFoundError("没有找到这条 LLM 调用记录。", code="llm_call_not_found")
    detail = AdminLlmCallDetailResponse.model_validate(row, from_attributes=True)
    detail.attempts = [
        AdminLlmAttempt.model_validate(a, from_attributes=True)
        for a in await store.attempts_for(call_id)
    ]
    if not include_payload:
        # Opt-in, because this is the one endpoint that returns resume content.
        detail.prompt_text = None
        detail.response_text = None
        detail.reasoning_text = None
    return detail


@router.get(
    "/llm/usage",
    response_model=AdminLlmUsageResponse,
    summary="LLM 用量汇总（按分类 / 调用方 / 真实模型分组）",
)
async def admin_llm_usage(
    days: int = Query(default=7, ge=1, le=90),
    group_by: str = Query(
        default="scenario",
        pattern="^(scenario|caller|channel|final_model|status)$",
    ),
    _: UserActor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminLlmUsageResponse:
    rows = await LlmCallStore(db).usage_rollup(days=days, group_by=group_by)
    return AdminLlmUsageResponse(
        group_by=group_by,
        days=days,
        rows=[AdminLlmUsageRow.model_validate(row) for row in rows],
    )


@router.get(
    "/sessions/{session_id}/trace.jsonl",
    summary="会话完整消息台账导出（NDJSON，每行一个事件）",
    response_class=PlainTextResponse,
)
async def admin_export_session_trace(
    session_id: str,
    limit: int = Query(
        default=5000,
        ge=1,
        le=5000,
        description="最多导出的事件行数，按 seq 升序。",
    ),
    _: UserActor = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """Replay-ready export of `jc_agent_trace`: one JSON object per line, in `seq` order.

    This is the read side of the append-only ledger described in
    `jc.models.agent_trace` — concatenating every row for a session and replaying
    them in `seq` order reconstructs the full system/user/assistant/tool message
    sequence DeerFlow actually sent and received, the same guarantee naviforge's
    `TraceRecord` export gives for its own sessions. NDJSON (one row per line,
    `\\n`-joined, no enclosing `[...]`) rather than a single JSON array: a 5000-row
    session should be `tail`-able and diffable line by line, and an NDJSON file
    does not require buffering the whole array in memory to parse the next line —
    both matter once this is the thing an operator opens to debug a user's report.

    `payload`/`attachments` are returned in full, never truncated — this table's
    one rule (see its docstring) is that it is not allowed to already be lossy,
    so an export that trimmed it here would quietly defeat the reason the table
    exists. `include_payload`-style gating (as `GET /admin/llm/calls/{id}` does)
    is intentionally not offered: this endpoint's entire purpose is to let an
    operator read exactly what a session said, and admin access is already gated
    by `require_admin`.
    """
    rows = await AgentTraceStore(db).list_for_session(session_id, limit=limit)
    lines = [
        json.dumps(
            {
                "id": row.id,
                "session_id": row.session_id,
                "seq": row.seq,
                "user_id": row.user_id,
                "profile_id": row.profile_id,
                "job_id": row.job_id,
                "mock_session_id": row.mock_session_id,
                "trace_id": row.trace_id,
                "llm_call_id": row.llm_call_id,
                "event_type": row.event_type,
                "role": row.role,
                "payload": row.payload,
                "attachments": row.attachments,
                "created_at": row.created_at.isoformat(),
            },
            ensure_ascii=False,
        )
        for row in rows
    ]
    body = "\n".join(lines)
    if body:
        body += "\n"
    return PlainTextResponse(
        content=body,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="{session_id}-trace.jsonl"',
        },
    )


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="用户目录（邮箱/显示名搜索）",
)
async def admin_list_users(
    limit: _Limit = 50,
    offset: _Offset = 0,
    search: Annotated[str | None, Query(description="按邮箱或显示名模糊匹配")] = None,
    sort_by: _UserSortBy = None,
    sort_dir: _SortDir = None,
    _: UserActor = Depends(require_admin),
    service: AdminUserService = Depends(get_admin_user_service),
) -> AdminUserListResponse:
    return await service.list_users(
        limit=limit,
        offset=offset,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
    summary="用户详情（含档案列表）",
)
async def admin_get_user(
    user_id: str,
    _: UserActor = Depends(require_admin),
    service: AdminUserService = Depends(get_admin_user_service),
) -> AdminUserDetailResponse:
    return await service.get_user(user_id)


@router.get(
    "/profiles/{profile_id}",
    response_model=ProfileResponse,
    summary="简历档案详情（完整结构化内容）",
)
async def admin_get_profile(
    profile_id: str,
    _: UserActor = Depends(require_admin),
    service: AdminUserService = Depends(get_admin_user_service),
) -> ProfileResponse:
    return await service.get_profile(profile_id)


@router.get(
    "/feedback",
    response_model=AdminFeedbackThreadListResponse,
    summary="用户反馈列表（可按状态筛选）",
)
async def admin_list_feedback(
    limit: _Limit = 50,
    offset: _Offset = 0,
    status: Annotated[str | None, Query(description="open/replying/resolved/closed")] = None,
    sort_by: _FeedbackSortBy = None,
    sort_dir: _SortDir = None,
    _: UserActor = Depends(require_admin),
    svc: FeedbackService = Depends(get_feedback_service),
) -> AdminFeedbackThreadListResponse:
    return await svc.admin_list(
        limit=limit,
        offset=offset,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get(
    "/feedback/{thread_id}",
    response_model=AdminFeedbackThreadDetailResponse,
    summary="反馈详情（含对话历史）",
)
async def admin_get_feedback(
    thread_id: str,
    _: UserActor = Depends(require_admin),
    svc: FeedbackService = Depends(get_feedback_service),
) -> AdminFeedbackThreadDetailResponse:
    return await svc.admin_get(thread_id=thread_id)


@router.post(
    "/feedback/{thread_id}/reply",
    response_model=AdminFeedbackThreadDetailResponse,
    summary="管理员回复反馈",
)
async def admin_reply_feedback(
    thread_id: str,
    body: AdminFeedbackReplyRequest,
    actor: UserActor = Depends(require_admin),
    svc: FeedbackService = Depends(get_feedback_service),
) -> AdminFeedbackThreadDetailResponse:
    return await svc.admin_reply(
        admin_user_id=actor.user_id, thread_id=thread_id, body=body.body
    )


@router.post(
    "/feedback/{thread_id}/status",
    response_model=AdminFeedbackThreadDetailResponse,
    summary="修改反馈状态",
)
async def admin_set_feedback_status(
    thread_id: str,
    body: AdminFeedbackStatusRequest,
    _: UserActor = Depends(require_admin),
    svc: FeedbackService = Depends(get_feedback_service),
) -> AdminFeedbackThreadDetailResponse:
    return await svc.admin_set_status(thread_id=thread_id, status=body.status)
