"""Agent trace ledger: jc_agent_trace — full-fidelity session replay."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "010_agent_trace"
down_revision: str | None = "009_llm_call_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same reasoning as jc_llm_call's payload columns (TEXT 64 KB is not enough
# once a resume-sized prompt or a tool result is involved).
_PAYLOAD = sa.Text().with_variant(LONGTEXT, "mysql")


def upgrade() -> None:
    op.create_table(
        "jc_agent_trace",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("jc_agent_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=True),
        sa.Column("profile_id", sa.String(32), nullable=True),
        sa.Column("job_id", sa.String(32), nullable=True),
        sa.Column("mock_session_id", sa.String(32), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("llm_call_id", sa.String(32), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("payload", _PAYLOAD, nullable=False),
        sa.Column("attachments", _PAYLOAD, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_jc_agent_trace_session_seq", "jc_agent_trace", ["session_id", "seq"], unique=True
    )
    op.create_index("ix_jc_agent_trace_user_created", "jc_agent_trace", ["user_id", "created_at"])
    op.create_index("ix_jc_agent_trace_trace_id", "jc_agent_trace", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_jc_agent_trace_trace_id", table_name="jc_agent_trace")
    op.drop_index("ix_jc_agent_trace_user_created", table_name="jc_agent_trace")
    op.drop_index("ix_jc_agent_trace_session_seq", table_name="jc_agent_trace")
    op.drop_table("jc_agent_trace")
