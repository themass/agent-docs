"""Add inbox_state_json to jc_user_meta."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_inbox_state"
down_revision: Union[str, None] = "002_agent_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jc_user_meta", sa.Column("inbox_state_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jc_user_meta", "inbox_state_json")
