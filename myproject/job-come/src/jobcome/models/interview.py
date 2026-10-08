"""Interview flywheel models."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobcome.db.base import Base
from jobcome.db.mixins import TimestampMixin
from jobcome.db.types import JSONText
from jobcome.models.enums import ApplicationStatus, MockSessionStatus, QuestionSource

if TYPE_CHECKING:
    from jobcome.models.profile import Profile


class InterviewRecord(Base, TimestampMixin):
    __tablename__ = "jc_interview_record"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    round: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    interview_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    failure_tags: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_ids: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    resume_variant_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="interview_records")
    questions: Mapped[list[InterviewQuestion]] = relationship(back_populates="interview_record")


class InterviewQuestion(Base, TimestampMixin):
    __tablename__ = "jc_interview_question"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), default=QuestionSource.REAL, nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    round: Mapped[str | None] = mapped_column(String(16), nullable=True)
    interview_record_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("jc_interview_record.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tags: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    best_attempt_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="interview_questions")
    interview_record: Mapped[InterviewRecord | None] = relationship(back_populates="questions")
    attempts: Mapped[list[AnswerAttempt]] = relationship(back_populates="question")


class AnswerAttempt(Base, TimestampMixin):
    __tablename__ = "jc_answer_attempt"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    question_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_interview_question.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mock_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    coach_feedback: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False, default=dict)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_best: Mapped[bool] = mapped_column(default=False, nullable=False)

    question: Mapped[InterviewQuestion] = relationship(back_populates="attempts")


class MockSession(Base, TimestampMixin):
    __tablename__ = "jc_mock_session"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    resume_variant_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    round: Mapped[str | None] = mapped_column(String(16), nullable=True)
    question_ids: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    bank_draw_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=MockSessionStatus.ACTIVE, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deerflow_thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="mock_sessions")


class Application(Base, TimestampMixin):
    __tablename__ = "jc_application"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_jc_application_profile_job"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resume_variant_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applied_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=ApplicationStatus.EVALUATED, nullable=False, index=True
    )
    user_marked: Mapped[bool] = mapped_column(default=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class OfferTrack(Base, TimestampMixin):
    __tablename__ = "jc_offer_track"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
