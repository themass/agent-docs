"""Add job_id to jc_agent_session."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_agent_session_job_id"
down_revision: Union[str, None] = "003_user_inbox_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jc_agent_session", sa.Column("job_id", sa.String(32), nullable=True))
    op.create_index("ix_jc_agent_session_job_id", "jc_agent_session", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_jc_agent_session_job_id", table_name="jc_agent_session")
    op.drop_column("jc_agent_session", "job_id")
