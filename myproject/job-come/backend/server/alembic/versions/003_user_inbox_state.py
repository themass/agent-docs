"""Add inbox_state_json to jc_user_meta."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_inbox_state"
down_revision: str | None = "002_agent_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jc_user_meta", sa.Column("inbox_state_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jc_user_meta", "inbox_state_json")
