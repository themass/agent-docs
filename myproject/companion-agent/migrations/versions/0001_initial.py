"""initial schema（D §3、O §2.1、O §10）。由 scripts/gen_ddl.py 从 schema.py 生成，勿手改。

MySQL 5.6 兼容：无 JSON 列，表名统一带 ca_ 前缀（共用 vpn 库）。

Postgres（目标库，全新建库）：0001 直接建出截至 0003 的完整结构（UPGRADE_SQL_PG），
0002、0003 在 Postgres 上不做任何事。之后的迁移对两种方言都生效。
"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE ca_account_purge_log (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_hash VARCHAR(64) NOT NULL, 
	requested_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_action_confirmation (
	id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	turn_id VARCHAR(26), 
	tool VARCHAR(64) NOT NULL, 
	args MEDIUMTEXT, 
	args_fingerprint VARCHAR(16) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	summary TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	decided_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_agent_job (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	kind VARCHAR(64) NOT NULL, 
	payload MEDIUMTEXT, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER NOT NULL DEFAULT '0', 
	max_attempts INTEGER NOT NULL DEFAULT '5', 
	run_after DATETIME NOT NULL, 
	lease_owner VARCHAR(64), 
	lease_until DATETIME, 
	dedupe_key VARCHAR(191), 
	last_error TEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_job_dedupe UNIQUE (dedupe_key)
);
CREATE TABLE ca_chat_message (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	`role` VARCHAR(16) NOT NULL, 
	content MEDIUMTEXT NOT NULL, 
	kind VARCHAR(16) NOT NULL DEFAULT 'chat', 
	meta MEDIUMTEXT, 
	client_message_id VARCHAR(64), 
	turn_id VARCHAR(26), 
	interrupted BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	deleted BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_message_client_id UNIQUE (session_id, client_message_id)
);
CREATE TABLE ca_chat_queue (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	message_id BIGINT NOT NULL, 
	client_message_id VARCHAR(64), 
	text MEDIUMTEXT NOT NULL, 
	attachments MEDIUMTEXT, 
	status VARCHAR(16) NOT NULL, 
	turn_id VARCHAR(26), 
	drain_attempts INTEGER NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_chat_session (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	name VARCHAR(128) NOT NULL DEFAULT '', 
	locale VARCHAR(16) NOT NULL DEFAULT 'zh-CN', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	deleted BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id)
);
CREATE TABLE ca_chat_turn (
	id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	state VARCHAR(16) NOT NULL, 
	model VARCHAR(128), 
	prompt_version VARCHAR(32), 
	role_id VARCHAR(128), 
	skills MEDIUMTEXT, 
	`usage` MEDIUMTEXT, 
	error_code VARCHAR(64), 
	started_at DATETIME, 
	finished_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_persona_profile (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	app VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	markdown MEDIUMTEXT NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	generated_from MEDIUMTEXT, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_persona_version UNIQUE (owner_id, app, version)
);
CREATE TABLE ca_tool_call (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	turn_id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	tool VARCHAR(64) NOT NULL, 
	permission VARCHAR(16) NOT NULL, 
	args_fingerprint VARCHAR(16) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	latency_ms INTEGER, 
	result_chars INTEGER, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_upload (
	id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	object_key VARCHAR(255) NOT NULL, 
	mime VARCHAR(64) NOT NULL, 
	size BIGINT NOT NULL, 
	width INTEGER, 
	height INTEGER, 
	referenced BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_user_role (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	public_id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	tagline VARCHAR(120) NOT NULL DEFAULT '', 
	description TEXT NOT NULL, 
	prompt MEDIUMTEXT NOT NULL, 
	locale VARCHAR(16) NOT NULL DEFAULT 'zh-CN', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	deleted BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	UNIQUE (public_id)
);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ca_user_role;
DROP TABLE IF EXISTS ca_upload;
DROP TABLE IF EXISTS ca_tool_call;
DROP TABLE IF EXISTS ca_persona_profile;
DROP TABLE IF EXISTS ca_chat_turn;
DROP TABLE IF EXISTS ca_chat_session;
DROP TABLE IF EXISTS ca_chat_queue;
DROP TABLE IF EXISTS ca_chat_message;
DROP TABLE IF EXISTS ca_agent_job;
DROP TABLE IF EXISTS ca_action_confirmation;
DROP TABLE IF EXISTS ca_account_purge_log;
"""


UPGRADE_SQL_PG = """
CREATE TABLE ca_timeline_event (
	id BIGSERIAL NOT NULL, 
	public_id VARCHAR(26) NOT NULL UNIQUE, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	session_id BIGINT, 
	source_message_id VARCHAR(26), 
	origin VARCHAR(16) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	title VARCHAR(60) NOT NULL, 
	at_utc TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	timezone VARCHAR(64) NOT NULL DEFAULT 'UTC', 
	all_day BOOLEAN NOT NULL DEFAULT FALSE, 
	recurrence VARCHAR(16) NOT NULL DEFAULT 'none', 
	next_at_utc TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(16) NOT NULL DEFAULT 'scheduled', 
	confidence REAL NOT NULL DEFAULT 1, 
	reminder_id BIGINT, 
	dedupe_key VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_timeline_dedupe UNIQUE (owner_id, role_id, dedupe_key)
);
CREATE INDEX ca_ix_timeline_owner_role_next ON ca_timeline_event (owner_id, role_id, status, next_at_utc);
CREATE INDEX ca_ix_timeline_source ON ca_timeline_event (source_message_id);
CREATE TABLE ca_account_purge_log (
	id BIGSERIAL NOT NULL, 
	user_hash VARCHAR(64) NOT NULL, 
	requested_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_action_confirmation (
	id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	turn_id VARCHAR(26), 
	tool VARCHAR(64) NOT NULL, 
	args JSONB, 
	args_fingerprint VARCHAR(16) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	summary TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	decided_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_confirm_owner_status ON ca_action_confirmation (owner_id, status);
CREATE INDEX ca_ix_confirm_status_expires ON ca_action_confirmation (status, expires_at);
CREATE TABLE ca_agent_job (
	id BIGSERIAL NOT NULL, 
	kind VARCHAR(64) NOT NULL, 
	payload JSONB, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	max_attempts INTEGER DEFAULT '5' NOT NULL, 
	run_after TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	lease_owner VARCHAR(64), 
	lease_until TIMESTAMP WITHOUT TIME ZONE, 
	dedupe_key VARCHAR(191), 
	last_error TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_job_dedupe UNIQUE (dedupe_key)
);
CREATE INDEX ca_ix_job_status_run_after ON ca_agent_job (status, run_after);
CREATE TABLE ca_chat_message (
	id BIGSERIAL NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	content TEXT NOT NULL, 
	kind VARCHAR(16) DEFAULT 'chat' NOT NULL, 
	meta JSONB, 
	client_message_id VARCHAR(64), 
	turn_id VARCHAR(26), 
	interrupted BOOLEAN DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	deleted BOOLEAN DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_message_client_id UNIQUE (session_id, client_message_id)
);
CREATE INDEX ca_ix_message_session_deleted_id ON ca_chat_message (session_id, deleted, id);
CREATE TABLE ca_chat_queue (
	id BIGSERIAL NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	message_id BIGINT NOT NULL, 
	client_message_id VARCHAR(64), 
	text TEXT NOT NULL, 
	attachments JSONB, 
	status VARCHAR(16) NOT NULL, 
	turn_id VARCHAR(26), 
	drain_attempts INTEGER DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_queue_session_status_id ON ca_chat_queue (session_id, status, id);
CREATE TABLE ca_chat_session (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	name VARCHAR(128) DEFAULT '' NOT NULL, 
	locale VARCHAR(16) DEFAULT 'zh-CN' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	deleted BOOLEAN DEFAULT '0' NOT NULL, 
	fence BIGINT DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_session_owner_deleted_updated ON ca_chat_session (owner_id, deleted, updated_at);
CREATE TABLE ca_chat_turn (
	id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	state VARCHAR(16) NOT NULL, 
	model VARCHAR(128), 
	prompt_version VARCHAR(32), 
	role_id VARCHAR(128), 
	skills JSONB, 
	usage JSONB, 
	error_code VARCHAR(64), 
	started_at TIMESTAMP WITHOUT TIME ZONE, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_turn_state_started ON ca_chat_turn (state, started_at);
CREATE TABLE ca_memory_item (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	content TEXT NOT NULL, 
	source_character_id VARCHAR(64) DEFAULT '' NOT NULL, 
	source_message_id VARCHAR(64) DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE ca_persona_profile (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	app VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	markdown TEXT NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	generated_from JSONB, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_persona_version UNIQUE (owner_id, app, version)
);
CREATE TABLE ca_reminder (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	due_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL, 
	content TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	lease_owner VARCHAR(64), 
	lease_until TIMESTAMP WITHOUT TIME ZONE, 
	confirmation_id VARCHAR(40), 
	sent_turn_id VARCHAR(26), 
	last_error TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_reminder_confirmation UNIQUE (confirmation_id)
);
CREATE INDEX ca_ix_reminder_owner_status ON ca_reminder (owner_id, status);
CREATE INDEX ca_ix_reminder_status_due ON ca_reminder (status, due_at);
CREATE TABLE ca_tool_call (
	id BIGSERIAL NOT NULL, 
	turn_id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	tool VARCHAR(64) NOT NULL, 
	permission VARCHAR(16) NOT NULL, 
	args_fingerprint VARCHAR(16) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	latency_ms INTEGER, 
	result_chars INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_toolcall_created ON ca_tool_call (created_at);
CREATE INDEX ca_ix_toolcall_turn ON ca_tool_call (turn_id);
CREATE TABLE ca_upload (
	id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	object_key VARCHAR(255) NOT NULL, 
	mime VARCHAR(64) NOT NULL, 
	size BIGINT NOT NULL, 
	width INTEGER, 
	height INTEGER, 
	referenced BOOLEAN DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_upload_owner ON ca_upload (owner_id);
CREATE TABLE ca_user_role (
	id BIGSERIAL NOT NULL, 
	public_id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	tagline VARCHAR(120) DEFAULT '' NOT NULL, 
	description TEXT NOT NULL, 
	prompt TEXT NOT NULL, 
	locale VARCHAR(16) DEFAULT 'zh-CN' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	deleted BOOLEAN DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (public_id)
);
CREATE INDEX ca_ix_role_owner_deleted ON ca_user_role (owner_id, deleted);
"""

DOWNGRADE_SQL_PG = """
DROP TABLE IF EXISTS ca_timeline_event;
DROP TABLE IF EXISTS ca_user_role;
DROP TABLE IF EXISTS ca_upload;
DROP TABLE IF EXISTS ca_tool_call;
DROP TABLE IF EXISTS ca_reminder;
DROP TABLE IF EXISTS ca_persona_profile;
DROP TABLE IF EXISTS ca_memory_item;
DROP TABLE IF EXISTS ca_chat_turn;
DROP TABLE IF EXISTS ca_chat_session;
DROP TABLE IF EXISTS ca_chat_queue;
DROP TABLE IF EXISTS ca_chat_message;
DROP TABLE IF EXISTS ca_agent_job;
DROP TABLE IF EXISTS ca_action_confirmation;
DROP TABLE IF EXISTS ca_account_purge_log;
"""


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    sql = UPGRADE_SQL_PG if _is_pg() else UPGRADE_SQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    sql = DOWNGRADE_SQL_PG if _is_pg() else DOWNGRADE_SQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)

