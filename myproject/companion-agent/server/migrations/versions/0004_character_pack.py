"""0004：ca_character_pack（角色封装落库，2026-11-27）。

随包发布的角色卡以前只活在磁盘上（agent/characters/*.v2.json），进程读一次缓存到死：
「每个角色的封装在服务端、在数据库里」这条没有成立。这张表把封装搬进库：完整 V2 卡
一份 payload，外加 renderer / pack_asset 两个**技术判别**列（客户端按它选数字人引擎、
找形象包）。播种工具 tools/seed_character_packs.py 把随包文件导进来，部署跑一次。

DDL 用 IF NOT EXISTS：基线（0001）已经带上这张表，新库跑这条时表已存在；已经跑过旧基线
的环境（线上库当前在 0003_message_feedback）靠这条补建。两条路径都安全，与 0002 同理。
表结构以 src/companion/db/schema.py 为准（守卫测试 tests/test_baseline_matches_schema.py
盯着基线与 schema 的一致性）。
"""

from alembic import op

revision = "0004_character_pack"
down_revision = "0003_message_feedback"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_character_pack (
	id BIGSERIAL NOT NULL,
	role_id VARCHAR(128) NOT NULL,
	payload JSONB NOT NULL,
	renderer VARCHAR(32) DEFAULT '' NOT NULL,
	pack_asset VARCHAR(128) DEFAULT '' NOT NULL,
	pack_version INTEGER DEFAULT '1' NOT NULL,
	source VARCHAR(32) DEFAULT '' NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_character_pack_role UNIQUE (role_id)
);
"""

MYSQL = """
CREATE TABLE IF NOT EXISTS ca_character_pack (
	id BIGINT NOT NULL AUTO_INCREMENT,
	role_id VARCHAR(128) NOT NULL,
	payload MEDIUMTEXT NOT NULL,
	renderer VARCHAR(32) NOT NULL DEFAULT '',
	pack_asset VARCHAR(128) NOT NULL DEFAULT '',
	pack_version INTEGER NOT NULL DEFAULT '1',
	source VARCHAR(32) NOT NULL DEFAULT '',
	created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT ca_uq_character_pack_role UNIQUE (role_id)
);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ca_character_pack")
