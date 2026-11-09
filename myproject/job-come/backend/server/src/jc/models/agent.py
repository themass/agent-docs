"""Agent session mapping."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import UTCDateTime
from jc.models.enums import AgentSessionStatus

if TYPE_CHECKING:
    from jc.models.user import User


class AgentSession(Base, TimestampMixin):
    __tablename__ = "jc_agent_session"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profile_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default=AgentSessionStatus.ACTIVE, nullable=False
    )
    deerflow_thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    #: The agent (a role id in roles.yaml) this session runs as. Its turn skill is not stored here.
    role_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    #: A stop request from any worker. The process running the session polls it (see
    #: `run_once` in deerflow_harness_client); a run that started before it is cancelled.
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="agent_sessions")
