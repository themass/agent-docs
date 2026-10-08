"""Application funnel: status + follow_up_on, one row per job."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_application_funnel"
down_revision: str | None = "006_job_fit_report"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jc_application",
        sa.Column("status", sa.String(16), nullable=False, server_default="evaluated"),
    )
    op.add_column("jc_application", sa.Column("follow_up_on", sa.Date(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE jc_application SET status = 'applied' WHERE applied_at IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            """
            DELETE a FROM jc_application a
            INNER JOIN jc_application b
              ON a.profile_id = b.profile_id
             AND a.job_id = b.job_id
             AND a.id > b.id
            """
        )
    )
    op.create_index("ix_jc_application_status", "jc_application", ["status"])
    op.create_unique_constraint(
        "uq_jc_application_profile_job",
        "jc_application",
        ["profile_id", "job_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_jc_application_profile_job", "jc_application", type_="unique")
    op.drop_index("ix_jc_application_status", table_name="jc_application")
    op.drop_column("jc_application", "follow_up_on")
    op.drop_column("jc_application", "status")
