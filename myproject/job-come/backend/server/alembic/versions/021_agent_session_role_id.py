"""Agent sessions: the column that names the agent a session runs as is `role_id`.

It was called `skill_hint`, but it has always held a role's id. The per-turn skill is recorded
separately, in the LLM call log. The rename changes no values.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_agent_session_role_id"
down_revision: str | None = "020_resume_reviewer_verdicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "jc_agent_session",
        "skill_hint",
        new_column_name="role_id",
        existing_type=sa.String(64),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "jc_agent_session",
        "role_id",
        new_column_name="skill_hint",
        existing_type=sa.String(64),
        existing_nullable=True,
    )
