"""Prevent long assistant replies/confirmation payloads exceeding MySQL TEXT."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision = "015_agent_message_longtext"
down_revision = "014_profile_patch_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite TEXT already has no 64KB limit; only MySQL needs this widening.
    if op.get_bind().dialect.name == "mysql":
        for column in ("content", "payload_json"):
            op.alter_column("jc_agent_message", column, existing_type=sa.Text(),
                            type_=LONGTEXT(), existing_nullable=True)


def downgrade() -> None:
    # Intentionally retain the widened columns: shrinking could truncate audit
    # history. The old application is fully compatible with LONGTEXT.
    pass
