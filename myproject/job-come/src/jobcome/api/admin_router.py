"""Admin / internal debug routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from jobcome.api.deps import get_session_audit_service, require_admin
from jobcome.schemas.admin_session import (
    AdminCheckpointResponse,
    AdminInventoryResponse,
    AdminSessionDetailResponse,
    AdminSessionListResponse,
    AdminTimelineResponse,
)
from jobcome.services.harness_inventory_service import build_harness_inventory
from jobcome.services.session_audit_service import SessionAuditService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/sessions",
    response_model=AdminSessionListResponse,
    summary="列出全部 Agent 会话（不限用户）",
)
async def admin_list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: str | None = Query(default=None),
    _: None = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminSessionListResponse:
    return await audit.list_sessions(limit=limit, offset=offset, user_id=user_id)


@router.get(
    "/sessions/{session_id}",
    response_model=AdminSessionDetailResponse,
    summary="会话详情",
)
async def admin_get_session(
    session_id: str,
    _: None = Depends(require_admin),
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
    _: None = Depends(require_admin),
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
    _: None = Depends(require_admin),
    audit: SessionAuditService = Depends(get_session_audit_service),
) -> AdminCheckpointResponse:
    return await audit.get_checkpoint(session_id)


@router.get(
    "/inventory",
    response_model=AdminInventoryResponse,
    summary="MCP / Tool / Skill / Middleware 清单",
)
async def admin_harness_inventory(
    _: None = Depends(require_admin),
) -> AdminInventoryResponse:
    return build_harness_inventory()
