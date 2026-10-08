"""Coach / interview routes."""

from __future__ import annotations

from typing import Annotated

from agentkit.web.auth import Actor, UserActor
from fastapi import APIRouter, Depends, Path, Query

from jobcome.api.deps import get_actor, get_coach_service, require_user
from jobcome.schemas.coach import (
    AnswerAttemptRequest,
    AnswerAttemptResponse,
    BankSearchResponse,
    InterviewSaveRequest,
    InterviewSaveResponse,
    MockRubricResponse,
    MockSessionCreateRequest,
    MockSessionResponse,
    QuestionDetailResponse,
    QuestionSummary,
    QuestionUpsertRequest,
)
from jobcome.services.interview_service import InterviewService

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get(
    "/rubric/mock",
    response_model=MockRubricResponse,
    summary="模拟面五维评分 rubric",
)
async def mock_interview_rubric() -> MockRubricResponse:
    from jobcome.coach.feedback import DIMENSION_KEYS, load_mock_rubric_markdown

    return MockRubricResponse(
        dimensions=list(DIMENSION_KEYS),
        markdown=load_mock_rubric_markdown(),
    )


@router.get(
    "/profiles/{profile_id}/bank",
    response_model=BankSearchResponse,
    summary="搜索题库",
)
async def search_bank(
    profile_id: Annotated[str, Path(description="档案 ID")],
    query: str = Query(default=""),
    company: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    actor: Actor = Depends(get_actor),
    coach: InterviewService = Depends(get_coach_service),
) -> BankSearchResponse:
    return await coach.search_bank(
        profile_id, actor=actor, query=query, company=company, job_id=job_id, limit=limit
    )


@router.get(
    "/questions/{question_id}",
    response_model=QuestionDetailResponse,
    summary="题目详情与练习记录",
)
async def get_question_detail(
    question_id: Annotated[str, Path(description="题目 ID")],
    actor: Actor = Depends(get_actor),
    coach: InterviewService = Depends(get_coach_service),
) -> QuestionDetailResponse:
    return await coach.get_question_detail(question_id, actor=actor)


@router.post(
    "/profiles/{profile_id}/interviews",
    response_model=InterviewSaveResponse,
    summary="归档真实面试",
)
async def save_interview(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: InterviewSaveRequest,
    actor: Actor = Depends(get_actor),
    coach: InterviewService = Depends(get_coach_service),
) -> InterviewSaveResponse:
    return await coach.save_interview(profile_id, actor=actor, body=body)


@router.post(
    "/questions/{question_id}/attempts",
    response_model=AnswerAttemptResponse,
    summary="保存练习作答",
)
async def save_attempt(
    question_id: Annotated[str, Path(description="题目 ID")],
    body: AnswerAttemptRequest,
    actor: Actor = Depends(get_actor),
    coach: InterviewService = Depends(get_coach_service),
) -> AnswerAttemptResponse:
    return await coach.save_attempt(question_id, actor=actor, body=body)


@router.post(
    "/mock/sessions",
    response_model=MockSessionResponse,
    summary="创建模拟面试会话",
)
async def create_mock_session(
    body: MockSessionCreateRequest,
    actor: UserActor = Depends(require_user),
    coach: InterviewService = Depends(get_coach_service),
) -> MockSessionResponse:
    return await coach.create_mock_session(actor=actor, body=body)


@router.get(
    "/mock/sessions/{session_id}",
    response_model=MockSessionResponse,
    summary="读取模拟面会话（含抽库题）",
)
async def get_mock_session(
    session_id: Annotated[str, Path(description="模拟会话 ID")],
    actor: UserActor = Depends(require_user),
    coach: InterviewService = Depends(get_coach_service),
) -> MockSessionResponse:
    return await coach.get_mock_session(session_id, actor=actor)


@router.post(
    "/profiles/{profile_id}/questions",
    response_model=QuestionSummary,
    summary="补记题目到个人题库",
)
async def log_question(
    profile_id: Annotated[str, Path(description="档案 ID")],
    body: QuestionUpsertRequest,
    actor: UserActor = Depends(require_user),
    coach: InterviewService = Depends(get_coach_service),
) -> QuestionSummary:
    return await coach.log_question(profile_id, actor=actor, body=body)
