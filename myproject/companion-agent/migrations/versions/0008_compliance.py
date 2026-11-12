"""0008：合规底座（ca_user_consent、ca_usage_span）。

依据《人工智能拟人化互动服务管理暂行办法》：训练用途单独同意、主动联系总开关、
连续使用提醒（办法 2 小时；纽约 GBL 3 小时，取最严）。这不是法律意见，上线前须法务核对。
"""

from alembic import op

revision = "0008_compliance"
down_revision = "0007_persona"
branch_labels = None
depends_on = None

PG = """
CREATE TABLE IF NOT EXISTS ca_user_consent (
	owner_id BIGINT PRIMARY KEY,
	training_consent BOOLEAN NOT NULL DEFAULT FALSE,
	proactive_enabled BOOLEAN NOT NULL DEFAULT TRUE,
	age_verified_adult BOOLEAN NOT NULL DEFAULT FALSE,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ca_usage_span (
	owner_id BIGINT PRIMARY KEY,
	started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	last_seen_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	reminded_at TIMESTAMP WITHOUT TIME ZONE,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

MYSQL = """
CREATE TABLE ca_user_consent (
	owner_id BIGINT NOT NULL,
	training_consent BOOL NOT NULL DEFAULT 0,
	proactive_enabled BOOL NOT NULL DEFAULT 1,
	age_verified_adult BOOL NOT NULL DEFAULT 0,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (owner_id)
);
CREATE TABLE ca_usage_span (
	owner_id BIGINT NOT NULL,
	started_at DATETIME NOT NULL,
	last_seen_at DATETIME NOT NULL,
	reminded_at DATETIME,
	updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (owner_id)
);
"""


def upgrade() -> None:
    sql = PG if op.get_bind().dialect.name == "postgresql" else MYSQL
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ca_usage_span")
    op.execute("DROP TABLE IF EXISTS ca_user_consent")
