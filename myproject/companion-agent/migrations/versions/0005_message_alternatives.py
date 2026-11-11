"""0005：消息的候选回复（ca_chat_message.alt_group / alt_selected），左右滑动切换回答用。

Postgres 的 0001 基线不含这两列，所以两种库都要加；用 IF NOT EXISTS 让重复执行无害。
"""

from alembic import op

revision = "0005_message_alternatives"
down_revision = "0004_timeline"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_pg():
        op.execute("ALTER TABLE ca_chat_message ADD COLUMN IF NOT EXISTS alt_group BIGINT")
        op.execute("ALTER TABLE ca_chat_message ADD COLUMN IF NOT EXISTS alt_selected BOOLEAN NOT NULL DEFAULT TRUE")
        op.execute("CREATE INDEX IF NOT EXISTS ca_ix_message_alt_group ON ca_chat_message (alt_group)")
        return
    op.execute("ALTER TABLE ca_chat_message ADD COLUMN alt_group BIGINT NULL")
    op.execute("ALTER TABLE ca_chat_message ADD COLUMN alt_selected BOOL NOT NULL DEFAULT 1")
    op.execute("CREATE INDEX ca_ix_message_alt_group ON ca_chat_message (alt_group)")


def downgrade() -> None:
    if _is_pg():
        op.execute("DROP INDEX IF EXISTS ca_ix_message_alt_group")
        op.execute("ALTER TABLE ca_chat_message DROP COLUMN IF EXISTS alt_selected")
        op.execute("ALTER TABLE ca_chat_message DROP COLUMN IF EXISTS alt_group")
        return
    op.execute("DROP INDEX ca_ix_message_alt_group ON ca_chat_message")
    op.execute("ALTER TABLE ca_chat_message DROP COLUMN alt_selected")
    op.execute("ALTER TABLE ca_chat_message DROP COLUMN alt_group")
