"""0001 基线：全部 ca_ 表。

产品未上线、没有线上数据，所以十个增量迁移（0001–0010）在这里合并成一个基线，
而不是保留一串「为历史服务」的补丁。这样做的好处：
- 新环境一条 upgrade head 就是最终形态，不需要重放十次 ALTER；
- 时间列统一是 timestamptz（以前是 timestamp without time zone，读回不带时区，
  和带时区的 now 一比较就崩）；
- 表结构可以直接读，不必在十个文件之间拼凑一张表长什么样。

以后加字段照常写新的迁移：有默认值的 ADD COLUMN 对已有数据是安全的，
不需要为了「兼容旧数据」预先塞一堆 JSON 列。
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

PG = """
CREATE TABLE ca_account_purge_log (
	id BIGSERIAL NOT NULL, 
	user_hash VARCHAR(64) NOT NULL, 
	requested_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
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
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	decided_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_confirm_status_expires ON ca_action_confirmation (status, expires_at);

CREATE INDEX ca_ix_confirm_owner_status ON ca_action_confirmation (owner_id, status);

CREATE TABLE ca_agent_job (
	id BIGSERIAL NOT NULL, 
	kind VARCHAR(64) NOT NULL, 
	payload JSONB, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	max_attempts INTEGER DEFAULT '5' NOT NULL, 
	run_after TIMESTAMP WITH TIME ZONE NOT NULL, 
	lease_owner VARCHAR(64), 
	lease_until TIMESTAMP WITH TIME ZONE, 
	dedupe_key VARCHAR(191), 
	last_error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_job_dedupe UNIQUE (dedupe_key)
);

CREATE INDEX ca_ix_job_status_run_after ON ca_agent_job (status, run_after);

CREATE TABLE ca_avatar_release (
	id BIGSERIAL NOT NULL, 
	avatar_key VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	role_id VARCHAR(128) DEFAULT '' NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	manifest JSONB NOT NULL, 
	object_key VARCHAR(255) NOT NULL, 
	size_bytes BIGINT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	min_app_version INTEGER DEFAULT '0' NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_avatar_version UNIQUE (avatar_key, version)
);

CREATE INDEX ca_ix_avatar_status_role ON ca_avatar_release (status, role_id);

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
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	deleted BOOLEAN DEFAULT '0' NOT NULL, 
	alt_group BIGINT, 
	alt_selected BOOLEAN DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_message_client_id UNIQUE (session_id, client_message_id)
);

CREATE INDEX ca_ix_message_session_deleted_id ON ca_chat_message (session_id, deleted, id);

CREATE INDEX ca_ix_message_alt_group ON ca_chat_message (alt_group);

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
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_queue_session_status_id ON ca_chat_queue (session_id, status, id);

CREATE TABLE ca_chat_session (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	name VARCHAR(128) DEFAULT '' NOT NULL, 
	locale VARCHAR(16) DEFAULT 'zh-CN' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
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
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_turn_state_started ON ca_chat_turn (state, started_at);

CREATE TABLE ca_delivery_receipt (
	id VARCHAR(48) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	text TEXT NOT NULL, 
	channel VARCHAR(16) DEFAULT 'in_app' NOT NULL, 
	meta JSONB, 
	at TIMESTAMP WITH TIME ZONE NOT NULL, 
	drained_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_receipt_owner_drained_at ON ca_delivery_receipt (owner_id, drained_at, at);

CREATE TABLE ca_memory_item (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	content TEXT NOT NULL, 
	source_character_id VARCHAR(64) DEFAULT '' NOT NULL, 
	source_message_id VARCHAR(64) DEFAULT '' NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	supersedes_id VARCHAR(64), 
	is_latest BOOLEAN DEFAULT '1' NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE ca_persona_cursor (
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	last_message_id BIGINT DEFAULT '0' NOT NULL, 
	pending_chars INTEGER DEFAULT '0' NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (owner_id, role_id)
);

CREATE TABLE ca_persona_entry (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	topic VARCHAR(32) NOT NULL, 
	memo VARCHAR(255) NOT NULL, 
	section VARCHAR(8) NOT NULL, 
	is_inference BOOLEAN DEFAULT '0' NOT NULL, 
	confidence FLOAT DEFAULT '0.8' NOT NULL, 
	source_fact_ids JSONB, 
	mentioned_at TIMESTAMP WITH TIME ZONE, 
	happened_at TIMESTAMP WITH TIME ZONE, 
	superseded_by BIGINT, 
	suppressed BOOLEAN DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_persona_owner_role ON ca_persona_entry (owner_id, role_id, superseded_by);

CREATE TABLE ca_persona_profile (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	app VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	markdown TEXT NOT NULL, 
	source VARCHAR(16) NOT NULL, 
	generated_from JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_persona_version UNIQUE (owner_id, app, version)
);

CREATE TABLE ca_proactive_prefs (
	owner_id BIGINT NOT NULL, 
	events_enabled BOOLEAN DEFAULT '1' NOT NULL, 
	greetings_enabled BOOLEAN DEFAULT '0' NOT NULL, 
	call_enabled BOOLEAN DEFAULT '0' NOT NULL, 
	quiet_start VARCHAR(5) DEFAULT '23:00' NOT NULL, 
	quiet_end VARCHAR(5) DEFAULT '08:00' NOT NULL, 
	max_per_day INTEGER DEFAULT '2' NOT NULL, 
	max_per_week INTEGER DEFAULT '6' NOT NULL, 
	paused_until TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (owner_id)
);

CREATE TABLE ca_reminder (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	session_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	due_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL, 
	content TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	attempts INTEGER DEFAULT '0' NOT NULL, 
	lease_owner VARCHAR(64), 
	lease_until TIMESTAMP WITH TIME ZONE, 
	confirmation_id VARCHAR(40), 
	sent_turn_id VARCHAR(26), 
	last_error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_reminder_confirmation UNIQUE (confirmation_id)
);

CREATE INDEX ca_ix_reminder_owner_status ON ca_reminder (owner_id, status);

CREATE INDEX ca_ix_reminder_status_due ON ca_reminder (status, due_at);

CREATE TABLE ca_send_record (
	id BIGSERIAL NOT NULL, 
	owner_id BIGINT NOT NULL, 
	at TIMESTAMP WITH TIME ZONE NOT NULL, 
	channel VARCHAR(16) NOT NULL, 
	trigger VARCHAR(64) DEFAULT '' NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_send_owner_at ON ca_send_record (owner_id, at);

CREATE TABLE ca_timeline_event (
	id BIGSERIAL NOT NULL, 
	public_id VARCHAR(26) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	session_id BIGINT, 
	source_message_id VARCHAR(26), 
	origin VARCHAR(16) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	title VARCHAR(60) NOT NULL, 
	at_utc TIMESTAMP WITH TIME ZONE NOT NULL, 
	timezone VARCHAR(64) DEFAULT 'UTC' NOT NULL, 
	all_day BOOLEAN DEFAULT '0' NOT NULL, 
	recurrence VARCHAR(16) DEFAULT 'none' NOT NULL, 
	next_at_utc TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(16) DEFAULT 'scheduled' NOT NULL, 
	confidence FLOAT DEFAULT '1' NOT NULL, 
	reminder_id BIGINT, 
	dedupe_key VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_timeline_dedupe UNIQUE (owner_id, role_id, dedupe_key), 
	UNIQUE (public_id)
);

CREATE INDEX ca_ix_timeline_owner_role_next ON ca_timeline_event (owner_id, role_id, status, next_at_utc);

CREATE INDEX ca_ix_timeline_source ON ca_timeline_event (source_message_id);

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
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
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
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_upload_owner ON ca_upload (owner_id);

CREATE TABLE ca_usage_span (
	owner_id BIGINT NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	reminded_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (owner_id)
);

CREATE TABLE ca_user_consent (
	owner_id BIGINT NOT NULL, 
	training_consent BOOLEAN DEFAULT '0' NOT NULL, 
	proactive_enabled BOOLEAN DEFAULT '1' NOT NULL, 
	age_verified_adult BOOLEAN DEFAULT '0' NOT NULL, 
	qa_retention BOOLEAN DEFAULT '0' NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (owner_id)
);

CREATE TABLE ca_user_role (
	id BIGSERIAL NOT NULL, 
	public_id VARCHAR(40) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	tagline VARCHAR(120) DEFAULT '' NOT NULL, 
	description TEXT NOT NULL, 
	prompt TEXT NOT NULL, 
	locale VARCHAR(16) DEFAULT 'zh-CN' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	deleted BOOLEAN DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (public_id)
);

CREATE INDEX ca_ix_role_owner_deleted ON ca_user_role (owner_id, deleted);

CREATE TABLE ca_llm_call (
	id BIGSERIAL NOT NULL, 
	turn_id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128), 
	seq INTEGER DEFAULT '0' NOT NULL, 
	provider VARCHAR(64), 
	model VARCHAR(128), 
	prompt_version VARCHAR(32), 
	content_kept BOOLEAN DEFAULT '0' NOT NULL, 
	input_messages JSONB, 
	output_text TEXT, 
	reasoning_text TEXT, 
	tool_calls JSONB, 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	cached_tokens INTEGER, 
	first_token_ms INTEGER, 
	total_ms INTEGER, 
	finish_reason VARCHAR(32), 
	error_code VARCHAR(64), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_llmcall_created ON ca_llm_call (created_at);

CREATE INDEX ca_ix_llmcall_owner_created ON ca_llm_call (owner_id, created_at);

CREATE INDEX ca_ix_llmcall_turn ON ca_llm_call (turn_id);

CREATE TABLE ca_voice_turn (
	id BIGSERIAL NOT NULL, 
	turn_id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128), 
	user_message_id BIGINT, 
	content_kept BOOLEAN DEFAULT '0' NOT NULL, 
	stt_provider VARCHAR(64), 
	stt_text TEXT, 
	stt_confidence FLOAT, 
	tts_provider VARCHAR(64), 
	tts_voice VARCHAR(128), 
	tts_text JSONB, 
	audio_in_key VARCHAR(255), 
	audio_out_key VARCHAR(255), 
	first_sentence_ms INTEGER, 
	tts_ttfb_ms INTEGER, 
	tts_audio_ms INTEGER, 
	tts_truncated BOOLEAN DEFAULT '0' NOT NULL, 
	total_ms INTEGER, 
	interrupted BOOLEAN DEFAULT '0' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_voiceturn_created ON ca_voice_turn (created_at);

CREATE INDEX ca_ix_voiceturn_owner_created ON ca_voice_turn (owner_id, created_at);

CREATE UNIQUE INDEX ca_uq_voiceturn_turn ON ca_voice_turn (turn_id);
"""

MYSQL = """
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

CREATE INDEX ca_ix_confirm_status_expires ON ca_action_confirmation (status, expires_at);

CREATE INDEX ca_ix_confirm_owner_status ON ca_action_confirmation (owner_id, status);

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

CREATE INDEX ca_ix_job_status_run_after ON ca_agent_job (status, run_after);

CREATE TABLE ca_avatar_release (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	avatar_key VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	role_id VARCHAR(128) NOT NULL DEFAULT '', 
	status VARCHAR(16) NOT NULL, 
	manifest MEDIUMTEXT NOT NULL, 
	object_key VARCHAR(255) NOT NULL, 
	size_bytes BIGINT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	min_app_version INTEGER NOT NULL DEFAULT '0', 
	published_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_avatar_version UNIQUE (avatar_key, version)
);

CREATE INDEX ca_ix_avatar_status_role ON ca_avatar_release (status, role_id);

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
	alt_group BIGINT, 
	alt_selected BOOL NOT NULL DEFAULT '1', 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_message_client_id UNIQUE (session_id, client_message_id)
);

CREATE INDEX ca_ix_message_alt_group ON ca_chat_message (alt_group);

CREATE INDEX ca_ix_message_session_deleted_id ON ca_chat_message (session_id, deleted, id);

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

CREATE INDEX ca_ix_queue_session_status_id ON ca_chat_queue (session_id, status, id);

CREATE TABLE ca_chat_session (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	name VARCHAR(128) NOT NULL DEFAULT '', 
	locale VARCHAR(16) NOT NULL DEFAULT 'zh-CN', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	deleted BOOL NOT NULL DEFAULT '0', 
	fence BIGINT NOT NULL DEFAULT '0', 
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
	skills MEDIUMTEXT, 
	`usage` MEDIUMTEXT, 
	error_code VARCHAR(64), 
	started_at DATETIME, 
	finished_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_turn_state_started ON ca_chat_turn (state, started_at);

CREATE TABLE ca_delivery_receipt (
	id VARCHAR(48) NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	text MEDIUMTEXT NOT NULL, 
	channel VARCHAR(16) NOT NULL DEFAULT 'in_app', 
	meta MEDIUMTEXT, 
	at DATETIME NOT NULL, 
	drained_at DATETIME, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_receipt_owner_drained_at ON ca_delivery_receipt (owner_id, drained_at, at);

CREATE TABLE ca_memory_item (
	id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64) NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	content TEXT NOT NULL, 
	source_character_id VARCHAR(64) NOT NULL DEFAULT '', 
	source_message_id VARCHAR(64) NOT NULL DEFAULT '', 
	created_at DATETIME NOT NULL, 
	supersedes_id VARCHAR(64), 
	is_latest BOOL NOT NULL DEFAULT '1', 
	PRIMARY KEY (id)
);

CREATE TABLE ca_persona_cursor (
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	last_message_id BIGINT NOT NULL DEFAULT '0', 
	pending_chars INTEGER NOT NULL DEFAULT '0', 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (owner_id, role_id)
);

CREATE TABLE ca_persona_entry (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128) NOT NULL, 
	topic VARCHAR(32) NOT NULL, 
	memo VARCHAR(255) NOT NULL, 
	section VARCHAR(8) NOT NULL, 
	is_inference BOOL NOT NULL DEFAULT '0', 
	confidence FLOAT NOT NULL DEFAULT '0.8', 
	source_fact_ids MEDIUMTEXT, 
	mentioned_at DATETIME, 
	happened_at DATETIME, 
	superseded_by BIGINT, 
	suppressed BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_persona_owner_role ON ca_persona_entry (owner_id, role_id, superseded_by);

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

CREATE TABLE ca_proactive_prefs (
	owner_id BIGINT NOT NULL, 
	events_enabled BOOL NOT NULL DEFAULT '1', 
	greetings_enabled BOOL NOT NULL DEFAULT '0', 
	call_enabled BOOL NOT NULL DEFAULT '0', 
	quiet_start VARCHAR(5) NOT NULL DEFAULT '23:00', 
	quiet_end VARCHAR(5) NOT NULL DEFAULT '08:00', 
	max_per_day INTEGER NOT NULL DEFAULT '2', 
	max_per_week INTEGER NOT NULL DEFAULT '6', 
	paused_until DATETIME, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (owner_id)
);

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

CREATE TABLE ca_send_record (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	owner_id BIGINT NOT NULL, 
	at DATETIME NOT NULL, 
	channel VARCHAR(16) NOT NULL, 
	`trigger` VARCHAR(64) NOT NULL DEFAULT '', 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_send_owner_at ON ca_send_record (owner_id, at);

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
	all_day BOOL NOT NULL DEFAULT '0', 
	recurrence VARCHAR(16) NOT NULL DEFAULT 'none', 
	next_at_utc DATETIME, 
	status VARCHAR(16) NOT NULL DEFAULT 'scheduled', 
	confidence FLOAT NOT NULL DEFAULT '1', 
	reminder_id BIGINT, 
	dedupe_key VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT ca_uq_timeline_dedupe UNIQUE (owner_id, role_id, dedupe_key), 
	UNIQUE (public_id)
);

CREATE INDEX ca_ix_timeline_source ON ca_timeline_event (source_message_id);

CREATE INDEX ca_ix_timeline_owner_role_next ON ca_timeline_event (owner_id, role_id, status, next_at_utc);

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

CREATE INDEX ca_ix_toolcall_turn ON ca_tool_call (turn_id);

CREATE INDEX ca_ix_toolcall_created ON ca_tool_call (created_at);

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

CREATE INDEX ca_ix_upload_owner ON ca_upload (owner_id);

CREATE TABLE ca_usage_span (
	owner_id BIGINT NOT NULL, 
	started_at DATETIME NOT NULL, 
	last_seen_at DATETIME NOT NULL, 
	reminded_at DATETIME, 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (owner_id)
);

CREATE TABLE ca_user_consent (
	owner_id BIGINT NOT NULL, 
	training_consent BOOL NOT NULL DEFAULT '0', 
	proactive_enabled BOOL NOT NULL DEFAULT '1', 
	age_verified_adult BOOL NOT NULL DEFAULT '0', 
	qa_retention BOOL NOT NULL DEFAULT '0', 
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (owner_id)
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

CREATE INDEX ca_ix_role_owner_deleted ON ca_user_role (owner_id, deleted);

CREATE TABLE ca_llm_call (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	turn_id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128), 
	seq INTEGER NOT NULL DEFAULT '0', 
	provider VARCHAR(64), 
	model VARCHAR(128), 
	prompt_version VARCHAR(32), 
	content_kept BOOL NOT NULL DEFAULT '0', 
	input_messages MEDIUMTEXT, 
	output_text MEDIUMTEXT, 
	reasoning_text MEDIUMTEXT, 
	tool_calls MEDIUMTEXT, 
	input_tokens INTEGER, 
	output_tokens INTEGER, 
	cached_tokens INTEGER, 
	first_token_ms INTEGER, 
	total_ms INTEGER, 
	finish_reason VARCHAR(32), 
	error_code VARCHAR(64), 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_llmcall_created ON ca_llm_call (created_at);

CREATE INDEX ca_ix_llmcall_owner_created ON ca_llm_call (owner_id, created_at);

CREATE INDEX ca_ix_llmcall_turn ON ca_llm_call (turn_id);

CREATE TABLE ca_voice_turn (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	turn_id VARCHAR(26) NOT NULL, 
	session_id BIGINT NOT NULL, 
	owner_id BIGINT NOT NULL, 
	role_id VARCHAR(128), 
	user_message_id BIGINT, 
	content_kept BOOL NOT NULL DEFAULT '0', 
	stt_provider VARCHAR(64), 
	stt_text MEDIUMTEXT, 
	stt_confidence FLOAT, 
	tts_provider VARCHAR(64), 
	tts_voice VARCHAR(128), 
	tts_text MEDIUMTEXT, 
	audio_in_key VARCHAR(255), 
	audio_out_key VARCHAR(255), 
	first_sentence_ms INTEGER, 
	tts_ttfb_ms INTEGER, 
	tts_audio_ms INTEGER, 
	tts_truncated BOOL NOT NULL DEFAULT '0', 
	total_ms INTEGER, 
	interrupted BOOL NOT NULL DEFAULT '0', 
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id)
);

CREATE INDEX ca_ix_voiceturn_created ON ca_voice_turn (created_at);

CREATE INDEX ca_ix_voiceturn_owner_created ON ca_voice_turn (owner_id, created_at);

CREATE UNIQUE INDEX ca_uq_voiceturn_turn ON ca_voice_turn (turn_id);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    from companion.adapters.store.sql.schema import metadata

    for table in reversed(metadata.sorted_tables):
        op.execute(f"DROP TABLE IF EXISTS {table.name}")
