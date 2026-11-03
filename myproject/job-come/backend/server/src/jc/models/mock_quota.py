"""Monthly full-run quota for mock interviews: one row per user per month that has taken a run."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base


class MockFullRunQuota(Base):
    __tablename__ = "jc_mock_full_run_quota"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.now()
    )
