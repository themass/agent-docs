"""0006：形象发布（ca_avatar_release）。服务端上下线形象包，客户端按角色下载。"""

from alembic import op

revision = "0006_avatar_release"
down_revision = "0005_message_alternatives"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_avatar_release (
	id BIGSERIAL NOT NULL,
	avatar_key VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	name VARCHAR(60) NOT NULL,
	role_id VARCHAR(128) NOT NULL DEFAULT '',
	status VARCHAR(16) NOT NULL,
	manifest JSONB NOT NULL,
	object_key VARCHAR(255) NOT NULL,
	size_bytes BIGINT NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	min_app_version INTEGER NOT NULL DEFAULT 0,
	published_at TIMESTAMP WITHOUT TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_avatar_version UNIQUE (avatar_key, version)
);
CREATE INDEX IF NOT EXISTS ca_ix_avatar_status_role ON ca_avatar_release (status, role_id);
"""

MYSQL = """
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
	min_app_version INTEGER NOT NULL DEFAULT 0,
	published_at DATETIME,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_avatar_version UNIQUE (avatar_key, version)
);
CREATE INDEX ca_ix_avatar_status_role ON ca_avatar_release (status, role_id);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ca_avatar_release")
