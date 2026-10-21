"""User-facing feedback inbox routes."""

from __future__ import annotations

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jc.api.deps import get_db, require_user
from jc.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackReplyRequest,
    FeedbackThreadDetailResponse,
    FeedbackThreadListResponse,
)
from jc.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def get_feedback_service(db: AsyncSession = Depends(get_db)) -> FeedbackService:
    return FeedbackService(db)


@router.post("", response_model=FeedbackThreadDetailResponse, summary="提交反馈")
async def create_feedback(
    body: FeedbackCreateRequest,
    actor: UserActor = Depends(require_user),
    svc: FeedbackService = Depends(get_feedback_service),
) -> FeedbackThreadDetailResponse:
    return await svc.create_thread(user_id=actor.user_id, body=body)


@router.get("", response_model=FeedbackThreadListResponse, summary="我的反馈列表")
async def list_feedback(
    actor: UserActor = Depends(require_user),
    svc: FeedbackService = Depends(get_feedback_service),
) -> FeedbackThreadListResponse:
    return await svc.list_for_user(user_id=actor.user_id)


@router.get(
    "/{thread_id}", response_model=FeedbackThreadDetailResponse, summary="反馈详情（含对话）"
)
async def get_feedback(
    thread_id: str,
    actor: UserActor = Depends(require_user),
    svc: FeedbackService = Depends(get_feedback_service),
) -> FeedbackThreadDetailResponse:
    return await svc.get_for_user(user_id=actor.user_id, thread_id=thread_id)


@router.post(
    "/{thread_id}/messages",
    response_model=FeedbackThreadDetailResponse,
    summary="追加留言",
)
async def add_feedback_message(
    thread_id: str,
    body: FeedbackReplyRequest,
    actor: UserActor = Depends(require_user),
    svc: FeedbackService = Depends(get_feedback_service),
) -> FeedbackThreadDetailResponse:
    return await svc.add_user_message(user_id=actor.user_id, thread_id=thread_id, body=body)
