"""Profile source parse_phase for ingest observability."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008_profile_source_parse_phase"
down_revision: str | None = "007_application_funnel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jc_profile_source",
        sa.Column("parse_phase", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jc_profile_source", "parse_phase")
