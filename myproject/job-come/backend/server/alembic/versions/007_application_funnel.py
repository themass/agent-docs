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
    # Keep the lowest id per (profile, job). Written as a NOT IN subquery rather
    # than MySQL's `DELETE a FROM ... INNER JOIN ...`: that syntax is MySQL-only
    # and this migration must also run on Postgres.
    op.execute(
        sa.text(
            """
            DELETE FROM jc_application
             WHERE id NOT IN (
                   SELECT keep_id FROM (
                       SELECT MIN(id) AS keep_id
                         FROM jc_application
                        GROUP BY profile_id, job_id
                   ) AS keep
             )
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
