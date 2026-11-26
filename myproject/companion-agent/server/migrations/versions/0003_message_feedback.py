"""0003：ca_chat_message 增加 feedback 列（「喜欢/不喜欢」持久化，2026-11-26）。

Android chatkit 的 FeedbackActions（ComposerActions.kt:102-119）以前只存内存里的
likedIds/dislikedIds，刷新即丢。列值域 NULL / 'like' / 'dislike'：一条消息只有一个
当前反馈、没有历史（切换即覆盖、NULL=取消），也不按反馈查询，所以不需要索引或单独的表。

DDL 用「存在即跳过」：基线（0001）已经带上这一列，新库跑这条时列已存在；已经跑过旧基线
的环境靠这条补上。两条路径都安全，与 0002 的 IF NOT EXISTS 是同一个道理。
表结构以 src/companion/db/schema.py 为准（守卫测试 tests/test_baseline_matches_schema.py
盯着基线与 schema 的一致性）。

**生产侧不会自动跑到这条**：线上库的 alembic 版本停在 0001_baseline，补列由部署时人工安排。
"""

from alembic import op

revision = "0003_message_feedback"
down_revision = "0002_role_card"
branch_labels = None
depends_on = None

# Postgres 原生支持 ADD COLUMN IF NOT EXISTS。
PG_UPGRADE = """
ALTER TABLE ca_chat_message ADD COLUMN IF NOT EXISTS feedback VARCHAR(16);
"""

# MySQL 没有 ADD COLUMN IF NOT EXISTS，查 information_schema 后再决定要不要 ALTER。
MYSQL_UPGRADE = """
SET @has_col = (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ca_chat_message' AND COLUMN_NAME = 'feedback');
SET @ddl = IF(@has_col = 0,
    'ALTER TABLE ca_chat_message ADD COLUMN feedback VARCHAR(16) NULL',
    'DO 0');
PREPARE ca_stmt FROM @ddl;
EXECUTE ca_stmt;
DEALLOCATE PREPARE ca_stmt;
"""


def upgrade() -> None:
    sql = PG_UPGRADE if op.get_bind().dialect.name == "postgresql" else MYSQL_UPGRADE
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    # 删列会丢反馈数据；这是这次改动的逆操作，只在明确要回退时执行。
    op.execute("ALTER TABLE ca_chat_message DROP COLUMN feedback")
