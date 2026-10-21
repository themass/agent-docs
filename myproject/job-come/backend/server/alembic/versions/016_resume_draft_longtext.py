"""Allow complete generated resume drafts to exceed MySQL TEXT's 64 KiB limit."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision = "016_resume_draft_longtext"
down_revision = "015_agent_message_longtext"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite TEXT is effectively unbounded for this use. MySQL TEXT is limited
    # to 65,535 bytes, which a bilingual draft or embedded photo can exceed.
    if op.get_bind().dialect.name == "mysql":
        for column in ("sections", "elevation_map"):
            op.alter_column(
                "jc_resume_draft",
                column,
                existing_type=sa.Text(),
                type_=LONGTEXT(),
                existing_nullable=False,
            )


def downgrade() -> None:
    # Do not shrink a production audit/document column: that can make existing
    # rows unreadable or silently truncate future drafts. The old application is
    # compatible with LONGTEXT, so this migration is intentionally irreversible.
    pass
