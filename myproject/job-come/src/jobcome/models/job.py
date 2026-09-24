"""Job and campaign models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text

from jobcome.db.types import JSONText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobcome.db.base import Base
from jobcome.db.mixins import TimestampMixin
from jobcome.models.enums import CampaignPhase, JobStatus, JobTag

if TYPE_CHECKING:
    from jobcome.models.profile import Profile
    from jobcome.models.resume import ResumeDraft


class Job(Base, TimestampMixin):
    __tablename__ = "jc_job"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False, default=dict)
    role_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    tag: Mapped[str] = mapped_column(String(16), default=JobTag.WARMUP, nullable=False)
    fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fit_recommendation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    fit_gaps: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    fit_blockers: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    fit_report: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.ACTIVE, nullable=False)

    profile: Mapped[Profile] = relationship(back_populates="jobs")
    resume_drafts: Mapped[list[ResumeDraft]] = relationship(back_populates="job")


class Campaign(Base, TimestampMixin):
    __tablename__ = "jc_campaign"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    phase: Mapped[str] = mapped_column(String(16), default=CampaignPhase.WARMUP, nullable=False)
    warmup_job_ids: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    target_job_ids: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    progress: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False, default=dict)
    target_unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="campaign")
