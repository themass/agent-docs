"""Guest session model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jobcome.db.base import Base
from jobcome.db.mixins import TimestampMixin

if TYPE_CHECKING:
    from jobcome.models.profile import Profile


class GuestSession(Base, TimestampMixin):
    __tablename__ = "jc_guest_session"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_by_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profiles: Mapped[list[Profile]] = relationship(back_populates="guest_session")


class PasswordResetToken(Base, TimestampMixin):
    __tablename__ = "jc_password_reset"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
