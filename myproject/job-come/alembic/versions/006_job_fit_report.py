"""Persist structured fit report on jc_job."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_job_fit_report"
down_revision: Union[str, None] = "005_user_active_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # MySQL TEXT/BLOB cannot use DEFAULT; add nullable then backfill.
    op.add_column("jc_job", sa.Column("fit_report", sa.Text(), nullable=True))
    op.execute(sa.text("UPDATE jc_job SET fit_report = '{}' WHERE fit_report IS NULL"))


def downgrade() -> None:
    op.drop_column("jc_job", "fit_report")
