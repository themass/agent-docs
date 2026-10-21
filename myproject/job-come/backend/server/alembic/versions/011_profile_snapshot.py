"""Profile snapshot ledger: jc_profile_snapshot — version history before payload overwrite."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "011_profile_snapshot"
down_revision: str | None = "010_agent_trace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same reasoning as jc_agent_trace's payload column (TEXT 64 KB is not enough
# once a resume-sized profile payload is involved).
_PAYLOAD = sa.Text().with_variant(LONGTEXT, "mysql")


def upgrade() -> None:
    op.create_table(
        "jc_profile_snapshot",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "profile_id",
            sa.String(32),
            sa.ForeignKey("jc_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_after", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(32), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("payload", _PAYLOAD, nullable=False),
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
        "ix_jc_profile_snapshot_profile_version",
        "jc_profile_snapshot",
        ["profile_id", "version_after"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_jc_profile_snapshot_profile_version", table_name="jc_profile_snapshot"
    )
    op.drop_table("jc_profile_snapshot")
