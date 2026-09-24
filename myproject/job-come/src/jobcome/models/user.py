"""User account models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobcome.db.base import Base
from jobcome.db.mixins import SoftDeleteMixin, TimestampMixin
from jobcome.models.enums import ElevationLevel, UserStatus

if TYPE_CHECKING:
    from jobcome.models.agent import AgentSession
    from jobcome.models.profile import Profile


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "jc_user"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=UserStatus.ACTIVE, nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meta: Mapped[UserMeta | None] = relationship(back_populates="user", uselist=False)
    profiles: Mapped[list[Profile]] = relationship(back_populates="user")
    agent_sessions: Mapped[list[AgentSession]] = relationship(back_populates="user")


class UserMeta(Base, TimestampMixin):
    __tablename__ = "jc_user_meta"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_user.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    locale: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)
    default_elevation_level: Mapped[str] = mapped_column(
        String(16), default=ElevationLevel.ELEVATED, nullable=False
    )
    active_profile_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="SET NULL"), nullable=True
    )
    notify_email_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    inbox_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="meta")
