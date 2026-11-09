"""Agent sessions: a stop request is recorded on the session, so any worker can see it.

A run lives in the worker process that started it, and an in-process event cannot reach a run in
another worker. `cancel_requested_at` is the request itself: the stop endpoint writes it, and the
process running the session polls it while the run is alive.

Nullable, so existing rows need no backfill. The column is added only if it is missing, so the
migration can be run again (MySQL does not roll back column changes).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_agent_cancel_request"
down_revision: str | None = "024_mock_report_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "jc_agent_session"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    present = {c["name"] for c in inspector.get_columns(_TABLE)}
    if "cancel_requested_at" not in present:
        op.add_column(_TABLE, sa.Column("cancel_requested_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    present = {c["name"] for c in inspector.get_columns(_TABLE)}
    if "cancel_requested_at" in present:
        op.drop_column(_TABLE, "cancel_requested_at")
