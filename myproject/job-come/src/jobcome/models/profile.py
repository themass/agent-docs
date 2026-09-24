"""Profile models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobcome.db.base import Base
from jobcome.db.mixins import SoftDeleteMixin, TimestampMixin
from jobcome.db.types import JSONText
from jobcome.models.enums import OwnerKind, ParseStatus, ProfileStatus

if TYPE_CHECKING:
    from jobcome.models.guest import GuestSession
    from jobcome.models.interview import InterviewQuestion, InterviewRecord, MockSession
    from jobcome.models.job import Campaign, Job
    from jobcome.models.resume import ResumeDraft
    from jobcome.models.user import User


class Profile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "jc_profile"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("jc_user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    guest_session_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("jc_guest_session.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_kind: Mapped[str] = mapped_column(String(8), default=OwnerKind.GUEST, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ProfileStatus.DRAFT, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONText, nullable=False, default=dict)
    summary_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="profiles")
    guest_session: Mapped[GuestSession | None] = relationship(back_populates="profiles")
    sources: Mapped[list[ProfileSource]] = relationship(back_populates="profile")
    resume_drafts: Mapped[list[ResumeDraft]] = relationship(back_populates="profile")
    jobs: Mapped[list[Job]] = relationship(back_populates="profile")
    campaign: Mapped[Campaign | None] = relationship(back_populates="profile", uselist=False)
    interview_records: Mapped[list[InterviewRecord]] = relationship(back_populates="profile")
    interview_questions: Mapped[list[InterviewQuestion]] = relationship(back_populates="profile")
    mock_sessions: Mapped[list[MockSession]] = relationship(back_populates="profile")


class ProfileSource(Base, TimestampMixin):
    __tablename__ = "jc_profile_source"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(16), default=ParseStatus.PENDING, nullable=False)
    parse_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    profile: Mapped[Profile] = relationship(back_populates="sources")
