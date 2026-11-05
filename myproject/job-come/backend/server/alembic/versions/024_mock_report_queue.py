"""Mock sessions: the report is generated in the background, so its state is on the session.

`report_status` is the queue (queued -> generating -> ready | failed), `report_attempts` caps the
runs, `report_claimed_at` is the lease of the worker holding it. Sessions that ended before this
migration are not queued: one with a stored report is `ready`, one without is `failed` with no
reason (the page words that case itself), so deploying does not start a model run for every old
session. The user can retry such a report.

MySQL does not roll back column changes. If a step after the first column fails, the columns stay
and the version does not move, so every step here checks what is already there and the migration
can be run again. It also writes no text: the table's character set is not ours to assume.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_mock_report_queue"
down_revision: str | None = "023_mock_session_level"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "jc_mock_session"
_INDEX = "ix_jc_mock_session_report_status"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    present = {c["name"] for c in inspector.get_columns(_TABLE)}
    for column in (
        sa.Column("report_status", sa.String(16), nullable=True),
        sa.Column("report_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_claimed_at", sa.DateTime(), nullable=True),
        sa.Column("report_error", sa.String(255), nullable=True),
    ):
        if column.name not in present:
            op.add_column(_TABLE, column)
    if _INDEX not in {i["name"] for i in inspector.get_indexes(_TABLE)}:
        op.create_index(_INDEX, _TABLE, ["report_status"])

    # Only rows nobody has touched: a re-run must not undo a retry or a finished report.
    has_report = "report IS NOT NULL AND report <> '' AND report <> '{}' AND report <> 'null'"
    op.execute(
        f"UPDATE {_TABLE} SET report_status = 'ready' "
        f"WHERE status = 'completed' AND report_status IS NULL AND {has_report}"
    )
    op.execute(
        f"UPDATE {_TABLE} SET report_status = 'failed' "
        f"WHERE status = 'completed' AND report_status IS NULL AND NOT ({has_report})"
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_column(_TABLE, "report_error")
    op.drop_column(_TABLE, "report_claimed_at")
    op.drop_column(_TABLE, "report_attempts")
    op.drop_column(_TABLE, "report_status")
