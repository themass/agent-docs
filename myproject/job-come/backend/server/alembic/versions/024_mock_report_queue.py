"""Mock sessions: the report is generated in the background, so its state is on the session.

`report_status` is the queue (queued -> generating -> ready | failed), `report_attempts` caps the
runs, `report_claimed_at` is the lease of the worker holding it. Sessions that ended before this
migration are not queued: one with a stored report is `ready`, one without is `failed` with a note,
so deploying does not start a model run for every old session. The user can retry such a report.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_mock_report_queue"
down_revision: str | None = "023_mock_session_level"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_NOTE = "历史场次，未生成报告"


def upgrade() -> None:
    op.add_column("jc_mock_session", sa.Column("report_status", sa.String(16), nullable=True))
    op.add_column(
        "jc_mock_session",
        sa.Column("report_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("jc_mock_session", sa.Column("report_claimed_at", sa.DateTime(), nullable=True))
    op.add_column("jc_mock_session", sa.Column("report_error", sa.String(255), nullable=True))
    op.create_index("ix_jc_mock_session_report_status", "jc_mock_session", ["report_status"])

    has_report = "report IS NOT NULL AND report <> '' AND report <> '{}' AND report <> 'null'"
    op.execute(
        f"UPDATE jc_mock_session SET report_status = 'ready' "
        f"WHERE status = 'completed' AND {has_report}"
    )
    op.execute(
        f"UPDATE jc_mock_session SET report_status = 'failed', report_error = '{_LEGACY_NOTE}' "
        f"WHERE status = 'completed' AND NOT ({has_report})"
    )


def downgrade() -> None:
    op.drop_index("ix_jc_mock_session_report_status", table_name="jc_mock_session")
    op.drop_column("jc_mock_session", "report_error")
    op.drop_column("jc_mock_session", "report_claimed_at")
    op.drop_column("jc_mock_session", "report_attempts")
    op.drop_column("jc_mock_session", "report_status")
