"""Mock sessions: the interview level the user chose (junior | mid | senior | expert).

Nullable: sessions created before levels existed have none, and nothing reads it for them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_mock_session_level"
down_revision: str | None = "022_drop_agent_session_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jc_mock_session", sa.Column("level", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("jc_mock_session", "level")
