"""Coach / interview API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class QuestionSummary(BaseModel):
    id: str
    stem: str
    question_type: str
    company: str | None = None
    job_id: str | None = None
    tags: list[Any] = []
    attempt_count: int = 0
    best_score: int | None = None
    from_bank: bool = False


class MockRubricResponse(BaseModel):
    dimensions: list[str]
    markdown: str


class BankSearchResponse(BaseModel):
    questions: list[QuestionSummary]


class InterviewSaveRequest(BaseModel):
    company: str = Field(min_length=1, max_length=256)
    role_title: str = Field(min_length=1, max_length=256)
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


class InterviewSummary(InterviewSaveRequest):
    id: str


class InterviewListResponse(BaseModel):
    interviews: list[InterviewSummary]


class MockSessionListItem(BaseModel):
    """A finished mock interview in the archive. Kept apart from real interviews."""

    id: str
    style: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    ended_reason: str | None = None
    ended_early: bool = False
    question_count: int
    has_report: bool


class MockSessionListResponse(BaseModel):
    mock_sessions: list[MockSessionListItem]


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
    job_id: str | None = None
    attempt_count: int
    best_score: int | None = None
    dimension_scores: dict[str, int] | None = None
    attempts: list[AnswerAttemptSummary]


class MockSessionCreateRequest(BaseModel):
    profile_id: str
    mode: Literal["warmup", "target"] = "target"
    round: str | None = None
    job_id: str | None = None
    #: "warmup" (5 questions, unlimited) or "full" (20 questions, metered for free accounts).
    #: Separate from `mode`, which is about the target job, not the length of the session.
    kind: Literal["warmup", "full"] = "warmup"
    #: The interviewer's manner (SPEC-MOCK-INTERVIEW §3). Changes how questions are put, never what
    #: is covered or how it is scored.
    style: Literal["gentle", "standard", "pressure", "deep"] = "standard"
    #: How deep the questions go (SPEC-MOCK-INTERVIEW-V2 §3.5). Left out, it is the level
    #: recommended from the profile; with no recommendation either, creation is refused.
    level: Literal["junior", "mid", "senior", "expert"] | None = None


class LevelOption(BaseModel):
    key: str
    label: str
    #: The P-series level it is compared with. A comparison, not an Alibaba standard.
    benchmark: str
    years: str
    requirement: str


class LevelRecommendationResponse(BaseModel):
    recommended: str | None = None
    years: float | None = None
    reason: str | None = None
    levels: list[LevelOption]


class MockSessionQuestion(BaseModel):
    id: str
    stem: str
    from_bank: bool = False
    attempt_count: int = 0


class MockSessionResponse(BaseModel):
    id: str
    profile_id: str
    mode: str
    status: str
    round: str | None
    job_id: str | None = None
    started_at: datetime
    level: str | None = None
    bank_draw_count: int = 0
    generated_count: int = 0
    questions: list[MockSessionQuestion] = Field(default_factory=list)


class QuestionUpsertRequest(BaseModel):
    source: Literal["real", "mock"] = "mock"
    stem: str = Field(min_length=4, max_length=4000)
    question_type: str = "behavioral"
    company: str | None = None
    role_title: str | None = None
    job_id: str | None = None
    mock_session_id: str | None = None
    round: str | None = None
    user_answer: str | None = None


class MockReportFix(BaseModel):
    severity: Literal["must", "suggest", "nit"]
    text: str


class MockReportReference(BaseModel):
    text: str
    source: str | None = None
    #: "sourced" when the fact was found in the profile; "pending" when it was not.
    status: Literal["sourced", "pending"]


class MockReportQuestion(BaseModel):
    question_id: str
    stem: str
    answer: str
    scores: dict[str, int | None]
    evidence: dict[str, str]
    praise: str | None = None
    fixes: list[MockReportFix] = Field(default_factory=list)
    reference: list[MockReportReference] = Field(default_factory=list)


class MockReportSuggestion(BaseModel):
    dimension: str
    label: str
    average: float
    practice: str
    #: The question where this dimension scored lowest, to open from the bank.
    question_id: str | None = None


class MockReportCoverage(BaseModel):
    total: int
    asked: int
    meet: int


class MockReportTrend(BaseModel):
    first_five: float | None
    last_five: float | None


class MockReportResponse(BaseModel):
    """The read-only report page. `status` is "active" while the session is still running,
    "pending" while the report is queued or being generated, "failed" when the review did not
    produce one (`can_retry` says whether the user may ask again), and "ready" once it is stored."""

    mock_session_id: str
    status: Literal["active", "pending", "failed", "ready"]
    can_retry: bool = False
    style: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    ended_reason: str | None = None
    ended_early: bool = False
    message: str | None = None
    overall: dict[str, float | None] = Field(default_factory=dict)
    checks: dict[str, int] = Field(default_factory=dict)
    #: A warm-up gets the brief report: the five averages and three suggestions, no per-question
    #: detail (SPEC §2).
    brief: bool = False
    questions: list[MockReportQuestion] = Field(default_factory=list)
    trend: MockReportTrend | None = None
    coverage: MockReportCoverage | None = None
    suggestions: list[MockReportSuggestion] = Field(default_factory=list)


class MockActionRequest(BaseModel):
    question_id: str


class MockActionResponse(BaseModel):
    """Result of skip or swap. A refusal carries its reason and writes nothing."""

    accepted: bool
    reason: str | None = None
    code: str | None = None
    swaps_left: int | None = None


class MockProgressResponse(BaseModel):
    style: str | None = None
    status: str
    asked_main: int
    main_limit: int
    remaining_main: int
    followups_by_parent: dict[str, int] = Field(default_factory=dict)
    must_have: list[str] = Field(default_factory=list)
    covered: list[str] = Field(default_factory=list)
    uncovered: list[str] = Field(default_factory=list)
    suggested_next: str | None = None
    current_question_id: str | None = None
    skipped: int = 0
    swaps_left: int = 0
