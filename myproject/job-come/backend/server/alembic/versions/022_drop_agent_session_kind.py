"""Agent sessions: drop `kind`. A session's agent (`role_id`) already says which group it belongs to.

`kind` was a UI grouping label (resume | coach) that the apply agent shared with the coach. Sessions
are now listed by agent, so the column carries nothing the role does not.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022_drop_agent_session_kind"
down_revision: str | None = "021_agent_session_role_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("jc_agent_session", "kind")


def downgrade() -> None:
    op.add_column(
        "jc_agent_session",
        sa.Column("kind", sa.String(16), nullable=False, server_default="resume"),
    )
