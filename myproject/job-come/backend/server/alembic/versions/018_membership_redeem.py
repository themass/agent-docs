"""Membership, redeem codes, download quota columns, app settings and admin audit log."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "018_membership_redeem"
down_revision: str | None = "017_profile_parse_lease"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.add_column("jc_user", sa.Column("vip_expires_at", sa.DateTime(), nullable=True))
    op.add_column("jc_user", sa.Column("free_download_used_at", sa.DateTime(), nullable=True))
    op.add_column("jc_user", sa.Column("free_download_job_id", sa.String(32), nullable=True))
    op.add_column("jc_user", sa.Column("free_download_reserved_at", sa.DateTime(), nullable=True))
    op.add_column(
        "jc_user",
        sa.Column("redeem_failed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("jc_user", sa.Column("redeem_locked_until", sa.DateTime(), nullable=True))

    op.create_table(
        "jc_redeem_code",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("batch_id", sa.String(32), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="unused"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("redeemed_by_user_id", sa.String(32), nullable=True),
        sa.Column("redeemed_at", sa.DateTime(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_jc_redeem_code_code"),
    )
    op.create_index("ix_jc_redeem_code_batch_id", "jc_redeem_code", ["batch_id"])
    op.create_index("ix_jc_redeem_code_status", "jc_redeem_code", ["status"])
    op.create_index(
        "ix_jc_redeem_code_redeemed_by_user_id", "jc_redeem_code", ["redeemed_by_user_id"]
    )

    op.create_table(
        "jc_membership_ledger",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("redeem_code_id", sa.String(32), nullable=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("redeem_code_id", name="uq_jc_membership_ledger_redeem_code"),
    )
    op.create_index("ix_jc_membership_ledger_user_id", "jc_membership_ledger", ["user_id"])

    op.create_table(
        "jc_app_setting",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(32), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "jc_admin_audit_log",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("actor_user_id", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_jc_admin_audit_log_actor_user_id", "jc_admin_audit_log", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_jc_admin_audit_log_actor_user_id", table_name="jc_admin_audit_log")
    op.drop_table("jc_admin_audit_log")
    op.drop_table("jc_app_setting")
    op.drop_index("ix_jc_membership_ledger_user_id", table_name="jc_membership_ledger")
    op.drop_table("jc_membership_ledger")
    op.drop_index("ix_jc_redeem_code_redeemed_by_user_id", table_name="jc_redeem_code")
    op.drop_index("ix_jc_redeem_code_status", table_name="jc_redeem_code")
    op.drop_index("ix_jc_redeem_code_batch_id", table_name="jc_redeem_code")
    op.drop_table("jc_redeem_code")
    op.drop_column("jc_user", "redeem_locked_until")
    op.drop_column("jc_user", "redeem_failed_count")
    op.drop_column("jc_user", "free_download_reserved_at")
    op.drop_column("jc_user", "free_download_job_id")
    op.drop_column("jc_user", "free_download_used_at")
    op.drop_column("jc_user", "vip_expires_at")
