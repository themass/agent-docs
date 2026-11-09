"""initial schema（D §3、O §2.1、O §10）。DDL 由 adapters/store/mysql/schema.py 生成，修改模型后重新生成。"""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE TABLE account_purge_log (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	user_hash VARCHAR(64) NOT NULL, 
	requested_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE action_confirmation (
	id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	turn_id VARCHAR(26), 
	tool VARCHAR(64) NOT NULL, 
	args JSON, 
	args_fingerprint VARCHAR(16) NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	summary TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	decided_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_confirm_status_expires ON action_confirmation (status, expires_at);

CREATE INDEX ix_confirm_owner_status ON action_confirmation (owner_id, status);

CREATE TABLE agent_job (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	kind VARCHAR(64) NOT NULL, 
	payload JSON, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER NOT NULL DEFAULT '0', 
	max_attempts INTEGER NOT NULL DEFAULT '5', 
	run_after DATETIME NOT NULL, 
	lease_owner VARCHAR(64), 
	lease_until DATETIME, 
	dedupe_key VARCHAR(191), 
	last_error TEXT, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_job_dedupe UNIQUE (dedupe_key)
);

CREATE INDEX ix_job_status_run_after ON agent_job (status, run_after);

CREATE TABLE chat_message (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	`role` VARCHAR(16) NOT NULL, 
	content MEDIUMTEXT NOT NULL, 
	kind VARCHAR(16) NOT NULL DEFAULT 'chat', 
	meta JSON, 
	client_message_id VARCHAR(64), 
	turn_id VARCHAR(26), 
	interrupted BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	deleted BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	CONSTRAINT uq_message_client_id UNIQUE (session_id, client_message_id)
);

CREATE INDEX ix_message_session_deleted_id ON chat_message (session_id, deleted, id);

CREATE TABLE chat_queue (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	message_id BIGINT NOT NULL, 
	client_message_id VARCHAR(64), 
	text MEDIUMTEXT NOT NULL, 
	attachments JSON, 
	status VARCHAR(16) NOT NULL, 
	turn_id VARCHAR(26), 
	drain_attempts INTEGER NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_queue_session_status_id ON chat_queue (session_id, status, id);

CREATE TABLE chat_session (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	name VARCHAR(128) NOT NULL DEFAULT '', 
	locale VARCHAR(16) NOT NULL DEFAULT 'zh-CN', 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	deleted BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id)
);

CREATE INDEX ix_session_owner_deleted_updated ON chat_session (owner_id, deleted, updated_at);

CREATE TABLE chat_turn (
	id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	state VARCHAR(16) NOT NULL, 
	model VARCHAR(128), 
	prompt_version VARCHAR(32), 
	role_id VARCHAR(128), 
	skills JSON, 
	`usage` JSON, 
	error_code VARCHAR(64), 
	started_at DATETIME, 
	finished_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_turn_state_started ON chat_turn (state, started_at);

CREATE TABLE persona_profile (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	app VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	markdown MEDIUMTEXT NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	generated_from JSON, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_persona_version UNIQUE (owner_id, app, version)
);

CREATE TABLE tool_call (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	turn_id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	tool VARCHAR(64) NOT NULL, 
	permission VARCHAR(16) NOT NULL, 
	args_fingerprint VARCHAR(16) NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	latency_ms INTEGER, 
	result_chars INTEGER, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_toolcall_turn ON tool_call (turn_id);

CREATE INDEX ix_toolcall_created ON tool_call (created_at);

CREATE TABLE upload (
	id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	object_key VARCHAR(255) NOT NULL, 
	mime VARCHAR(64) NOT NULL, 
	size BIGINT NOT NULL, 
	width INTEGER, 
	height INTEGER, 
	referenced BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_upload_owner ON upload (owner_id);

CREATE TABLE user_role (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	public_id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	tagline VARCHAR(120) NOT NULL DEFAULT '', 
	description TEXT NOT NULL, 
	prompt MEDIUMTEXT NOT NULL, 
	locale VARCHAR(16) NOT NULL DEFAULT 'zh-CN', 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	updated_at DATETIME NOT NULL DEFAULT (now()), 
	deleted BOOL NOT NULL DEFAULT '0', 
	PRIMARY KEY (id), 
	UNIQUE (public_id)
);

CREATE INDEX ix_role_owner_deleted ON user_role (owner_id, deleted);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS user_role;
DROP TABLE IF EXISTS upload;
DROP TABLE IF EXISTS tool_call;
DROP TABLE IF EXISTS persona_profile;
DROP TABLE IF EXISTS chat_turn;
DROP TABLE IF EXISTS chat_session;
DROP TABLE IF EXISTS chat_queue;
DROP TABLE IF EXISTS chat_message;
DROP TABLE IF EXISTS agent_job;
DROP TABLE IF EXISTS action_confirmation;
DROP TABLE IF EXISTS account_purge_log;
"""


def upgrade() -> None:
    for stmt in [s.strip() for s in UPGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in [s.strip() for s in DOWNGRADE_SQL.split(";") if s.strip()]:
        op.execute(stmt)
