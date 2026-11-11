"""0003：会话写入围栏（ca_chat_session.fence）与定时提醒表（ca_reminder）。

围栏见 chat-agent-context-design.md §4.2；提醒见 chat-agent-next-plan.md 阶段 4。
Postgres 的 0001 已包含这两项，这里只对 MySQL 生效。
"""

from alembic import op

revision = "0003_fence_reminder"
down_revision = "0002_memory_item"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
ALTER TABLE ca_chat_session ADD COLUMN fence BIGINT NOT NULL DEFAULT 0;
CREATE TABLE ca_reminder (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	due_at DATETIME NOT NULL, 
	timezone VARCHAR(64) NOT NULL DEFAULT 'UTC', 
	content TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER NOT NULL DEFAULT '0', 
	lease_owner VARCHAR(64), 
	lease_until DATETIME, 
	confirmation_id VARCHAR(40), 
	sent_turn_id VARCHAR(26), 
	last_error TEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_reminder_confirmation UNIQUE (confirmation_id)
);
CREATE INDEX ca_ix_reminder_owner_status ON ca_reminder (owner_id, status);
CREATE INDEX ca_ix_reminder_status_due ON ca_reminder (status, due_at);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ca_reminder;
ALTER TABLE ca_chat_session DROP COLUMN fence;
"""


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_pg():
        return
    for stmt in [s.strip() for s in UPGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    if _is_pg():
        return
    for stmt in [s.strip() for s in DOWNGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)
