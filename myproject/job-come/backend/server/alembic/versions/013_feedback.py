"""User feedback inbox: jc_feedback_thread (dashboard row) + jc_feedback_message (transcript)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013_feedback"
down_revision: str | None = "012_user_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jc_feedback_thread",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("jc_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(16), nullable=False, server_default="other"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("last_message_role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_jc_feedback_thread_user_id", "jc_feedback_thread", ["user_id"])
    op.create_index("ix_jc_feedback_thread_category", "jc_feedback_thread", ["category"])
    op.create_index("ix_jc_feedback_thread_status", "jc_feedback_thread", ["status"])
    op.create_index(
        "ix_jc_feedback_thread_status_last_message_at",
        "jc_feedback_thread",
        ["status", "last_message_at"],
    )

    op.create_table(
        "jc_feedback_message",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(32),
            sa.ForeignKey("jc_feedback_thread.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("author_user_id", sa.String(32), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_jc_feedback_message_thread_id", "jc_feedback_message", ["thread_id"])


def downgrade() -> None:
    op.drop_table("jc_feedback_message")
    op.drop_table("jc_feedback_thread")
