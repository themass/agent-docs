"""Durable, confirmation-gated write commands (not a transcript or cache)."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import JSONLongText


class ProfilePatchConfirm(Base, TimestampMixin):
    __tablename__ = "jc_profile_patch_confirm"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_agent_session.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_user.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_profile.id", ondelete="CASCADE"), nullable=False
    )
    patch: Mapped[dict] = mapped_column(JSONLongText, nullable=False)
    preview: Mapped[dict] = mapped_column(JSONLongText, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (
        Index("ix_jc_profile_patch_confirm_session", "session_id", "status"),
        Index("ix_jc_profile_patch_confirm_user", "user_id"),
        Index("ix_jc_profile_patch_confirm_profile", "profile_id"),
    )
