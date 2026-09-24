"""Coach / interview API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class QuestionSummary(BaseModel):
    id: str
    stem: str
    question_type: str
    company: str | None = None
    tags: list[Any] = []
    attempt_count: int = 0
    best_score: int | None = None


class MockRubricResponse(BaseModel):
    dimensions: list[str]
    markdown: str


class BankSearchResponse(BaseModel):
    questions: list[QuestionSummary]


class InterviewSaveRequest(BaseModel):
    company: str
    role_title: str
    interview_date: date
    round: str = "first"
    type: str = "target"
    job_id: str | None = None
    result: str | None = None
    failure_tags: list[str] = []
    notes: str | None = None
    question_ids: list[str] = []


class InterviewSaveResponse(BaseModel):
    id: str


class AnswerAttemptRequest(BaseModel):
    user_answer: str = Field(min_length=1)
    coach_feedback: dict[str, Any] | None = None
    reference_answer: str | None = None
    mock_session_id: str | None = None


class AnswerAttemptResponse(BaseModel):
    attempt_id: str
    question_id: str


class AnswerAttemptSummary(BaseModel):
    id: str
    user_answer: str
    coach_feedback: dict[str, Any] | None = None
    created_at: datetime
    is_best: bool = False


class QuestionDetailResponse(BaseModel):
    id: str
    stem: str
    question_type: str
    company: str | None = None
    attempt_count: int
    best_score: int | None = None
    dimension_scores: dict[str, int] | None = None
    attempts: list[AnswerAttemptSummary]


class MockSessionCreateRequest(BaseModel):
    profile_id: str
    mode: str = "target"
    round: str | None = None
    job_id: str | None = None


class MockSessionResponse(BaseModel):
    id: str
    profile_id: str
    mode: str
    status: str
    round: str | None
    started_at: datetime
