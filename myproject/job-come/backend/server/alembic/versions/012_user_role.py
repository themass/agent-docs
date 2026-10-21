"""Add jc_user.role — role-based admin access, defaulting every existing user to `user`."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_user_role"
down_revision: str | None = "011_profile_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jc_user",
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
    )


def downgrade() -> None:
    op.drop_column("jc_user", "role")
