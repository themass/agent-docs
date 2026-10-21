"""User feedback — a lightweight support inbox.

Two tables by design, not one:

- `FeedbackThread` is the summary/dashboard row: who opened it, what it's
  about, current lifecycle status, and who spoke last. Admin list and filter
  views query this table only — they never need to touch message bodies to
  render a dashboard.
- `FeedbackMessage` is the conversation log. Both the user's own thread view
  and the admin's drawer render the same rows; only the chrome around them
  (whose avatar is "me") differs by viewer.

This mirrors the `jc_agent_trace` (ledger) vs `jc_agent_message` (UI
projection) split used for agent sessions — a thread's current state should
be a cheap read, and the full transcript a separate, append-only one.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import UTCDateTime
from jc.models.enums import FeedbackCategory, FeedbackMessageRole, FeedbackStatus


class FeedbackThread(Base, TimestampMixin):
    __tablename__ = "jc_feedback_thread"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jc_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(16), default=FeedbackCategory.OTHER, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=FeedbackStatus.OPEN, nullable=False, index=True
    )
    # Denormalized onto the summary row so the admin list can sort/badge by
    # "needs a reply" without a join into messages.
    last_message_role: Mapped[str] = mapped_column(
        String(16), default=FeedbackMessageRole.USER, nullable=False
    )
    last_message_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    message_count: Mapped[int] = mapped_column(default=1, nullable=False)


class FeedbackMessage(Base, TimestampMixin):
    __tablename__ = "jc_feedback_message"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jc_feedback_thread.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # The admin who wrote an `admin`-role message, for accountability — null
    # for `user`-role rows.
    author_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
