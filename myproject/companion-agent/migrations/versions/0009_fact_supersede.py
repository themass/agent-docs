"""0009：事实记忆的「取代」（ca_memory_item.is_latest / supersedes_id）。

与画像同一套做法：新信息不删除旧条目，而是标为被取代、不再召回，保留回溯能力。
Postgres 的 0001 基线不含这两列，所以两种库都要加；Postgres 用 IF NOT EXISTS 让重复执行无害。
"""

from alembic import op

revision = "0009_fact_supersede"
down_revision = "0008_compliance"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_pg():
        op.execute("ALTER TABLE ca_memory_item ADD COLUMN IF NOT EXISTS supersedes_id VARCHAR(64)")
        op.execute("ALTER TABLE ca_memory_item ADD COLUMN IF NOT EXISTS is_latest BOOLEAN NOT NULL DEFAULT TRUE")
        return
    op.execute("ALTER TABLE ca_memory_item ADD COLUMN supersedes_id VARCHAR(64) NULL")
    op.execute("ALTER TABLE ca_memory_item ADD COLUMN is_latest BOOL NOT NULL DEFAULT 1")


def downgrade() -> None:
    if _is_pg():
        op.execute("ALTER TABLE ca_memory_item DROP COLUMN IF EXISTS is_latest")
        op.execute("ALTER TABLE ca_memory_item DROP COLUMN IF EXISTS supersedes_id")
        return
    op.execute("ALTER TABLE ca_memory_item DROP COLUMN is_latest")
    op.execute("ALTER TABLE ca_memory_item DROP COLUMN supersedes_id")
