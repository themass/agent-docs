"""Persist pending profile edits and their decision atomically with profile writes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "014_profile_patch_confirm"
down_revision: str | None = "013_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    longtext = sa.Text().with_variant(LONGTEXT(), "mysql")
    op.create_table(
        "jc_profile_patch_confirm",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("jc_agent_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("jc_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.String(32),
            sa.ForeignKey("jc_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("patch", longtext, nullable=False),
        sa.Column("preview", longtext, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("applied_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_jc_profile_patch_confirm_session", "jc_profile_patch_confirm", ["session_id", "status"]
    )
    op.create_index("ix_jc_profile_patch_confirm_user", "jc_profile_patch_confirm", ["user_id"])
    op.create_index(
        "ix_jc_profile_patch_confirm_profile", "jc_profile_patch_confirm", ["profile_id"]
    )


def downgrade() -> None:
    op.drop_table("jc_profile_patch_confirm")
