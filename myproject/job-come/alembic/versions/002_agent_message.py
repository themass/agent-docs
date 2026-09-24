"""Add jc_agent_message audit table."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_agent_message"
down_revision: Union[str, None] = "001_initial_jc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jc_agent_message",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("jc_agent_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False, server_default="message"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_jc_agent_message_session", "jc_agent_message", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_jc_agent_message_session", table_name="jc_agent_message")
    op.drop_table("jc_agent_message")
