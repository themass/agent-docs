"""0010：主动消息的三块持久化（ca_proactive_prefs、ca_delivery_receipt、ca_send_record）。

这三样原来都在进程内：偏好重启后恢复默认（用户关掉的主动消息又开了）、
收件箱消息用户还没看到就丢、投递账本多 worker 各自计数导致频控翻倍。
"""

from alembic import op

revision = "0010_proactive_store"
down_revision = "0009_fact_supersede"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_proactive_prefs (
	owner_id BIGINT NOT NULL,
	events_enabled BOOLEAN NOT NULL DEFAULT TRUE,
	greetings_enabled BOOLEAN NOT NULL DEFAULT FALSE,
	call_enabled BOOLEAN NOT NULL DEFAULT FALSE,
	quiet_start VARCHAR(5) NOT NULL DEFAULT '23:00',
	quiet_end VARCHAR(5) NOT NULL DEFAULT '08:00',
	max_per_day INTEGER NOT NULL DEFAULT 2,
	max_per_week INTEGER NOT NULL DEFAULT 6,
	paused_until TIMESTAMP WITHOUT TIME ZONE,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (owner_id)
);
CREATE TABLE IF NOT EXISTS ca_delivery_receipt (
	id VARCHAR(48) NOT NULL,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	text TEXT NOT NULL,
	channel VARCHAR(16) NOT NULL DEFAULT 'in_app',
	meta JSONB,
	at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	drained_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ca_ix_receipt_owner_drained_at ON ca_delivery_receipt (owner_id, drained_at, at);
CREATE TABLE IF NOT EXISTS ca_send_record (
	id BIGSERIAL NOT NULL,
	owner_id BIGINT NOT NULL,
	at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	channel VARCHAR(16) NOT NULL,
	trigger VARCHAR(64) NOT NULL DEFAULT '',
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ca_ix_send_owner_at ON ca_send_record (owner_id, at);
"""

MYSQL = """
CREATE TABLE IF NOT EXISTS ca_proactive_prefs (
	owner_id BIGINT NOT NULL,
	events_enabled BOOL NOT NULL DEFAULT 1,
	greetings_enabled BOOL NOT NULL DEFAULT 0,
	call_enabled BOOL NOT NULL DEFAULT 0,
	quiet_start VARCHAR(5) NOT NULL DEFAULT '23:00',
	quiet_end VARCHAR(5) NOT NULL DEFAULT '08:00',
	max_per_day INT NOT NULL DEFAULT 2,
	max_per_week INT NOT NULL DEFAULT 6,
	paused_until DATETIME NULL,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (owner_id)
) DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ca_delivery_receipt (
	id VARCHAR(48) NOT NULL,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	text MEDIUMTEXT NOT NULL,
	channel VARCHAR(16) NOT NULL DEFAULT 'in_app',
	meta MEDIUMTEXT,
	at DATETIME NOT NULL,
	drained_at DATETIME NULL,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	KEY ca_ix_receipt_owner_drained_at (owner_id, drained_at, at)
) DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS ca_send_record (
	id BIGINT NOT NULL AUTO_INCREMENT,
	owner_id BIGINT NOT NULL,
	at DATETIME NOT NULL,
	channel VARCHAR(16) NOT NULL,
	trigger VARCHAR(64) NOT NULL DEFAULT '',
	PRIMARY KEY (id),
	KEY ca_ix_send_owner_at (owner_id, at)
) DEFAULT CHARSET=utf8mb4;
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    for table in ("ca_send_record", "ca_delivery_receipt", "ca_proactive_prefs"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
