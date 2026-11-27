"""0005：ca_her_pack + ca_character_her（persona/her 分层第一刀，2026-11-28）。

persona 与 her 是两条线（docs/design/2026-11-28-persona-her-split-architecture.md）：
ca_character_pack 回答「她是谁」，呈现实体必须独立注册——renderer 长在包上而不是
角色上（用户自定义 her 只能走非 Live2D 引擎，这是 Live2D Expandable Application
条款下的法务必需），衣橱/特效/贴纸也要挂在模型包版本上才有挂载点。
这两张表 + /v1/hers 只是注册表与接口，不动任何现有 persona 链。

DDL 用 IF NOT EXISTS：基线（0001）已带这两张表，新库跑这条时表已存在；已有库
（线上当前 0004_character_pack）靠这条补建。与 0004 同理。
表结构以 src/companion/db/schema.py 为准（tests/test_baseline_matches_schema.py 盯一致性）。
"""

from alembic import op

revision = "0005_her_pack"
down_revision = "0004_character_pack"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_her_pack (
	id BIGSERIAL NOT NULL,
	her_id VARCHAR(128) NOT NULL,
	renderer VARCHAR(32) DEFAULT '' NOT NULL,
	pack_version INTEGER DEFAULT '1' NOT NULL,
	payload JSONB NOT NULL,
	status VARCHAR(16) DEFAULT 'draft' NOT NULL,
	source VARCHAR(32) DEFAULT '' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_her_pack_id UNIQUE (her_id)
);

CREATE TABLE IF NOT EXISTS ca_character_her (
	id BIGSERIAL NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	her_id VARCHAR(128) NOT NULL,
	is_default BOOLEAN DEFAULT '1' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_character_her_pair UNIQUE (role_id, her_id)
);
"""

MYSQL = """
CREATE TABLE IF NOT EXISTS ca_her_pack (
	id BIGINT NOT NULL AUTO_INCREMENT,
	her_id VARCHAR(128) NOT NULL,
	renderer VARCHAR(32) NOT NULL DEFAULT '',
	pack_version INTEGER NOT NULL DEFAULT '1',
	payload MEDIUMTEXT NOT NULL,
	status VARCHAR(16) NOT NULL DEFAULT 'draft',
	source VARCHAR(32) NOT NULL DEFAULT '',
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_her_pack_id UNIQUE (her_id)
);

CREATE TABLE IF NOT EXISTS ca_character_her (
	id BIGINT NOT NULL AUTO_INCREMENT,
	role_id VARCHAR(128) NOT NULL,
	her_id VARCHAR(128) NOT NULL,
	is_default BOOLEAN NOT NULL DEFAULT 1,
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_character_her_pair UNIQUE (role_id, her_id)
);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ca_character_her")
    op.execute("DROP TABLE IF EXISTS ca_her_pack")
