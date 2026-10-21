"""LLM call audit log: jc_llm_call + jc_llm_call_attempt."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "009_llm_call_log"
down_revision: str | None = "008_profile_source_parse_phase"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Prompts and responses exceed TEXT (64 KB) once a resume is involved, and CJK
# costs 3 bytes per character in utf8mb4.
_PAYLOAD = sa.Text().with_variant(LONGTEXT, "mysql")


def upgrade() -> None:
    op.create_table(
        "jc_llm_call",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=True),
        sa.Column("actor_kind", sa.String(16), nullable=True),
        sa.Column("profile_id", sa.String(32), nullable=True),
        sa.Column("job_id", sa.String(32), nullable=True),
        sa.Column("session_id", sa.String(32), nullable=True),
        sa.Column("scenario", sa.String(32), nullable=False),
        sa.Column("caller", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="router"),
        sa.Column("skill_hint", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("final_model", sa.String(128), nullable=True),
        sa.Column("final_provider", sa.String(32), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_micro_usd", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(32), nullable=True),
        sa.Column("stream", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("prompt_text", _PAYLOAD, nullable=True),
        sa.Column("response_text", _PAYLOAD, nullable=True),
        sa.Column("reasoning_text", _PAYLOAD, nullable=True),
        sa.Column(
            "payload_truncated", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
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
    op.create_index("ix_jc_llm_call_user_created", "jc_llm_call", ["user_id", "created_at"])
    op.create_index("ix_jc_llm_call_scenario_created", "jc_llm_call", ["scenario", "created_at"])
    op.create_index("ix_jc_llm_call_profile_created", "jc_llm_call", ["profile_id", "created_at"])
    op.create_index("ix_jc_llm_call_status_created", "jc_llm_call", ["status", "created_at"])
    op.create_index("ix_jc_llm_call_trace", "jc_llm_call", ["trace_id"])
    op.create_index("ix_jc_llm_call_created", "jc_llm_call", ["created_at"])

    op.create_table(
        "jc_llm_call_attempt",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("call_id", sa.String(32), nullable=False),
        sa.Column("attempt_index", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("api_base_env", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(1024), nullable=True),
        sa.Column(
            "validator_failed", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_micro_usd", sa.Integer(), nullable=True),
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
        "ix_jc_llm_call_attempt_call", "jc_llm_call_attempt", ["call_id", "attempt_index"]
    )


def downgrade() -> None:
    op.drop_index("ix_jc_llm_call_attempt_call", table_name="jc_llm_call_attempt")
    op.drop_table("jc_llm_call_attempt")
    for name in (
        "ix_jc_llm_call_created",
        "ix_jc_llm_call_trace",
        "ix_jc_llm_call_status_created",
        "ix_jc_llm_call_profile_created",
        "ix_jc_llm_call_scenario_created",
        "ix_jc_llm_call_user_created",
    ):
        op.drop_index(name, table_name="jc_llm_call")
    op.drop_table("jc_llm_call")
