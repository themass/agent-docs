"""Database claim lease for multi-instance profile parsing workers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017_profile_parse_lease"
down_revision: str | None = "016_resume_draft_longtext"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("jc_profile_source", sa.Column("parse_owner", sa.String(128), nullable=True))
    op.add_column("jc_profile_source", sa.Column("parse_claim_token", sa.String(64), nullable=True))
    op.add_column("jc_profile_source", sa.Column("parse_lease_until", sa.DateTime(), nullable=True))
    op.create_index("ix_jc_profile_source_parse_owner", "jc_profile_source", ["parse_owner"])
    op.create_index(
        "ix_jc_profile_source_parse_status_lease",
        "jc_profile_source",
        ["parse_status", "parse_lease_until"],
    )
    op.create_unique_constraint(
        "uq_jc_profile_source_parse_claim_token", "jc_profile_source", ["parse_claim_token"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_jc_profile_source_parse_claim_token", "jc_profile_source", type_="unique")
    op.drop_index("ix_jc_profile_source_parse_status_lease", table_name="jc_profile_source")
    op.drop_index("ix_jc_profile_source_parse_owner", table_name="jc_profile_source")
    op.drop_column("jc_profile_source", "parse_lease_until")
    op.drop_column("jc_profile_source", "parse_claim_token")
    op.drop_column("jc_profile_source", "parse_owner")
