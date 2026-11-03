"""Mock interview: monthly full-run quota and the session fields the spec needs."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "019_mock_interview_quota"
down_revision: str | None = "018_membership_redeem"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One row per user per calendar month (Asia/Shanghai) that has taken a full run. The primary
    # key is what makes the quota race-safe: two concurrent creates for the same month cannot both
    # insert, so only one of them can hold the run.
    op.create_table(
        "jc_mock_full_run_quota",
        sa.Column("user_id", sa.String(32), primary_key=True),
        sa.Column("month", sa.String(7), primary_key=True),
        sa.Column("session_id", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("jc_mock_session", sa.Column("style", sa.String(16), nullable=True))
    # JSON is stored as text, as every other JSON column in this project is (MySQL 5.6). A report
    # can run long, so it gets the LONGTEXT variant; coverage is small and fits TEXT.
    op.add_column("jc_mock_session", sa.Column("report", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True))
    op.add_column("jc_mock_session", sa.Column("coverage", sa.Text(), nullable=True))
    op.add_column(
        "jc_mock_session",
        sa.Column("quota_counted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("jc_mock_session", "quota_counted")
    op.drop_column("jc_mock_session", "coverage")
    op.drop_column("jc_mock_session", "report")
    op.drop_column("jc_mock_session", "style")
    op.drop_table("jc_mock_full_run_quota")
