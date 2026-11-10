"""0002：持久化记忆表 ca_memory_item（临时替代进程内记忆，见 adapters/store/mysql/memory.py）。

只新建一张表，不改动 0001 已建的表（0001 已在共用的 vpn 库上执行过）。
"""

from alembic import op

revision = "0002_memory_item"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE ca_memory_item (
	id VARCHAR(64) NOT NULL,
	user_id VARCHAR(64) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	content TEXT NOT NULL,
	source_character_id VARCHAR(64) NOT NULL DEFAULT '',
	source_message_id VARCHAR(64) NOT NULL DEFAULT '',
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	KEY ix_ca_memory_item_user_id (user_id, created_at)
);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ca_memory_item;
"""


def upgrade() -> None:
    for stmt in [s.strip() for s in UPGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in [s.strip() for s in DOWNGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)
