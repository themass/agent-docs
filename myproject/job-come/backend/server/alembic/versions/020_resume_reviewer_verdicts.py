"""Resume export review: the reviewer's verdict per track, written by the reviewer subtask.

The reviewer runs as a subtask in its own process (the MCP server), so its verdict has to be stored
where the web process can read it back. One JSON column holds the verdict for each track of the
draft (`zh` and `en` for a bilingual draft, `main` otherwise). It is cleared before each review, so
a draft that nobody checked this time has no verdict rather than a stale one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision: str = "020_resume_reviewer_verdicts"
down_revision: str | None = "019_mock_interview_quota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jc_resume_draft",
        sa.Column("reviewer_verdicts", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jc_resume_draft", "reviewer_verdicts")
