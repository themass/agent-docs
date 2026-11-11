"""0004：时间线持久化（ca_timeline_event，chat-agent-timeline-design.md）。

Postgres 的 0001 已直接建出这张表（重装库时一步到位）；这里只对 MySQL 生效，
并为已经建过库的 Postgres（0001 基线之后才加表的情况）做一次幂等创建。
"""

from alembic import op

revision = "0004_timeline"
down_revision = "0003_fence_reminder"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE ca_timeline_event (
	id BIGINT NOT NULL AUTO_INCREMENT,
	public_id VARCHAR(26) NOT NULL,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	session_id BIGINT,
	source_message_id VARCHAR(26),
	origin VARCHAR(16) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	title VARCHAR(60) NOT NULL,
	at_utc DATETIME NOT NULL,
	timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
	all_day BOOLEAN NOT NULL DEFAULT 0,
	recurrence VARCHAR(16) NOT NULL DEFAULT 'none',
	next_at_utc DATETIME,
	status VARCHAR(16) NOT NULL DEFAULT 'scheduled',
	confidence FLOAT NOT NULL DEFAULT 1,
	reminder_id BIGINT,
	dedupe_key VARCHAR(64) NOT NULL,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_timeline_dedupe UNIQUE (owner_id, role_id, dedupe_key)
);
CREATE UNIQUE INDEX ca_ix_timeline_public_id ON ca_timeline_event (public_id);
CREATE INDEX ca_ix_timeline_owner_role_next ON ca_timeline_event (owner_id, role_id, status, next_at_utc);
CREATE INDEX ca_ix_timeline_source ON ca_timeline_event (source_message_id);
"""

DOWNGRADE_SQL = "DROP TABLE IF EXISTS ca_timeline_event;"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 0001 的基线里已有这张表；这里只服务在 0004 之前就建好的库。
        from sqlalchemy import inspect

        if "ca_timeline_event" in inspect(bind).get_table_names():
            return
        from sqlalchemy.schema import CreateIndex, CreateTable

        from companion.adapters.store.sql.schema import timeline_event

        op.execute(CreateTable(timeline_event))
        for index in timeline_event.indexes:
            op.execute(CreateIndex(index))
        return
    for stmt in [s.strip() for s in UPGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
