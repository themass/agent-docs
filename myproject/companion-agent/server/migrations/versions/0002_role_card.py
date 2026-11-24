"""0002：P6 角色卡两张表（ca_role_card / ca_role_card_version）。

新库的基线（0001，已按本仓库惯例同步补上这两张表）已经建好它们；已经跑过旧基线的
环境靠这条补建。两条路径都安全，所以 DDL 用 IF NOT EXISTS——不依赖「这条只跑一次」，
也不依赖「基线一定先改」。表结构以 src/companion/db/schema.py 为准（守卫测试
tests/test_baseline_matches_schema.py 盯着基线与 schema 的一致性）。
"""

from alembic import op

revision = "0002_role_card"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_role_card (
	id BIGSERIAL NOT NULL,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	base JSONB NOT NULL,
	active_version INTEGER DEFAULT '1' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_role_card_owner_role UNIQUE (owner_id, role_id)
);

CREATE TABLE IF NOT EXISTS ca_role_card_version (
	id BIGSERIAL NOT NULL,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	version INTEGER NOT NULL,
	changes JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_role_card_version UNIQUE (owner_id, role_id, version)
);
"""

MYSQL = """
CREATE TABLE IF NOT EXISTS ca_role_card (
	id BIGINT NOT NULL AUTO_INCREMENT,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	base MEDIUMTEXT NOT NULL,
	active_version INTEGER NOT NULL DEFAULT '1',
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_role_card_owner_role UNIQUE (owner_id, role_id)
);

CREATE TABLE IF NOT EXISTS ca_role_card_version (
	id BIGINT NOT NULL AUTO_INCREMENT,
	owner_id BIGINT NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	version INTEGER NOT NULL,
	changes MEDIUMTEXT NOT NULL,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_role_card_version UNIQUE (owner_id, role_id, version)
);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ca_role_card_version")
    op.execute("DROP TABLE IF EXISTS ca_role_card")
