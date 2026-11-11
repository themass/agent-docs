"""0007：用户画像（ca_persona_entry、ca_persona_cursor）。"""

from alembic import op

revision = "0007_persona"
down_revision = "0006_avatar_release"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_persona_entry (
	id BIGSERIAL NOT NULL,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	topic VARCHAR(32) NOT NULL,
	memo VARCHAR(255) NOT NULL,
	section VARCHAR(8) NOT NULL,
	is_inference BOOLEAN NOT NULL DEFAULT FALSE,
	confidence REAL NOT NULL DEFAULT 0.8,
	source_fact_ids JSONB,
	mentioned_at TIMESTAMP WITHOUT TIME ZONE,
	happened_at TIMESTAMP WITHOUT TIME ZONE,
	superseded_by BIGINT,
	suppressed BOOLEAN NOT NULL DEFAULT FALSE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ca_ix_persona_owner_role ON ca_persona_entry (owner_id, role_id, superseded_by);
CREATE TABLE IF NOT EXISTS ca_persona_cursor (
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	last_message_id BIGINT NOT NULL DEFAULT 0,
	pending_chars INTEGER NOT NULL DEFAULT 0,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (owner_id, role_id)
);
"""

MYSQL = """
CREATE TABLE ca_persona_entry (
	id BIGINT NOT NULL AUTO_INCREMENT,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	topic VARCHAR(32) NOT NULL,
	memo VARCHAR(255) NOT NULL,
	section VARCHAR(8) NOT NULL,
	is_inference BOOL NOT NULL DEFAULT 0,
	confidence FLOAT NOT NULL DEFAULT 0.8,
	source_fact_ids MEDIUMTEXT,
	mentioned_at DATETIME,
	happened_at DATETIME,
	superseded_by BIGINT,
	suppressed BOOL NOT NULL DEFAULT 0,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id)
);
CREATE INDEX ca_ix_persona_owner_role ON ca_persona_entry (owner_id, role_id, superseded_by);
CREATE TABLE ca_persona_cursor (
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	last_message_id BIGINT NOT NULL DEFAULT 0,
	pending_chars INTEGER NOT NULL DEFAULT 0,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (owner_id, role_id)
);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ca_persona_cursor")
    op.execute("DROP TABLE IF EXISTS ca_persona_entry")
