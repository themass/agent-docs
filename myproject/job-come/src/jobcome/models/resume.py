"""Resume draft and export job models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String

from jobcome.db.types import JSONText
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobcome.db.base import Base
from jobcome.db.mixins import TimestampMixin
from jobcome.models.enums import ElevationLevel, ExportJobStatus, ReviewerStatus

if TYPE_CHECKING:
    from jobcome.models.job import Job
    from jobcome.models.profile import Profile


class ResumeDraft(Base, TimestampMixin):
    __tablename__ = "jc_resume_draft"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("jc_job.id", ondelete="SET NULL"), nullable=True, index=True
    )
    elevation_level: Mapped[str] = mapped_column(
        String(16), default=ElevationLevel.ELEVATED, nullable=False
    )
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sections: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False, default=dict)
    elevation_map: Mapped[list[Any]] = mapped_column(JSONText, nullable=False, default=list)
    reviewer_status: Mapped[str] = mapped_column(
        String(16), default=ReviewerStatus.PENDING, nullable=False
    )
    reviewer_notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="resume_drafts")
    job: Mapped[Job | None] = relationship(back_populates="resume_drafts")


class ExportJob(Base, TimestampMixin):
    __tablename__ = "jc_export_job"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resume_draft_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ExportJobStatus.PENDING, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
