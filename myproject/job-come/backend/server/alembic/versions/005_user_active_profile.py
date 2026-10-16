"""Add active_profile_id to jc_user_meta."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_user_active_profile"
down_revision: Union[str, None] = "004_agent_session_job_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jc_user_meta",
        sa.Column("active_profile_id", sa.String(32), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_meta_active_profile",
        "jc_user_meta",
        "jc_profile",
        ["active_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_user_meta_active_profile", "jc_user_meta", type_="foreignkey")
    op.drop_column("jc_user_meta", "active_profile_id")
