"""Direct-upload issuance ledger (ADR-011).

Creates `jc_media_upload`: one row per signed presigned-PUT, the server-side
fact that makes bind-time ownership checks (actor + scene + freshness) and the
GC sweep possible. No backfill — the table is new and empty by definition.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027_media_upload"
down_revision: str | None = "026_agent_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("jc_media_upload"):
        return  # half-applied deploy; the create below is what the model expects
    op.create_table(
        "jc_media_upload",
        sa.Column("object_key", sa.String(255), primary_key=True),
        sa.Column("actor_id", sa.String(32), nullable=False),
        sa.Column("actor_kind", sa.String(8), nullable=False),
        sa.Column("scene", sa.String(32), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("declared_size", sa.Integer(), nullable=False),
        sa.Column("actual_size", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bound_ref", sa.String(64), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_jc_media_upload_state_expires", "jc_media_upload", ["state", "expires_at"])
    op.create_index("ix_jc_media_upload_actor", "jc_media_upload", ["actor_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_jc_media_upload_actor", table_name="jc_media_upload")
    op.drop_index("ix_jc_media_upload_state_expires", table_name="jc_media_upload")
    op.drop_table("jc_media_upload")
