"""表结构（D §3、O §2.1、O §10）。Alembic 迁移从这里生成 DDL，见 migrations/versions/。

方言可移植：目标库是 Postgres；MySQL 保留为兼容方言（历史测试库）。两处方言差异都收在本文件：
- ``LongText``：Postgres 用 TEXT，MySQL 用 MEDIUMTEXT（TEXT 只有 64KB）；
- ``JsonText``：Postgres 用 JSONB，MySQL 5.6 没有 JSON 类型，以 MEDIUMTEXT 存储并编解码。
"""

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Index, Integer, MetaData, String, Table, Text,
    UniqueConstraint, Column, func, text, types,
)
import json

from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.dialects.postgresql import JSONB

# 共用的 vpn 库里有 Java 的表（chat_session、chat_message 等）：所有 companion 表都带这个前缀。
TABLE_PREFIX = "ca_"

metadata = MetaData(naming_convention={"ix": TABLE_PREFIX + "ix_%(column_0_name)s"})


LongText = Text().with_variant(MEDIUMTEXT(), "mysql")


class JsonText(types.TypeDecorator):
    """JSON 列。Postgres 用原生 JSONB；MySQL 5.6 没有 JSON 类型，以 MEDIUMTEXT 存储，读写时编解码。"""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        if dialect.name == "mysql":
            return dialect.type_descriptor(MEDIUMTEXT())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name == "postgresql":
            return value  # JSONB 由驱动编码
        return json.dumps(value, ensure_ascii=False, default=str)

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return None
        return json.loads(value) if isinstance(value, str) else value


_pk = lambda: Column("id", BigInteger, primary_key=True, autoincrement=True)  # noqa: E731
_now = lambda: Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))  # noqa: E731
_upd = lambda: Column("updated_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())  # noqa: E731

chat_session = Table(
    TABLE_PREFIX + "chat_session", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),
    Column("name", String(128), nullable=False, server_default=""),
    Column("locale", String(16), nullable=False, server_default="zh-CN"),
    _now(), _upd(),
    Column("deleted", Boolean, nullable=False, server_default="0"),
    # 写入围栏：每次拿到会话锁都会得到更大的围栏号；助手消息只在围栏号仍是最新时写入，
    # 锁过期后被别的进程接手的旧回合因此写不进来（chat-agent-context-design.md §4.2）。
    Column("fence", BigInteger, nullable=False, server_default="0"),
    Index("ca_ix_session_owner_deleted_updated", "owner_id", "deleted", "updated_at"),
)

chat_message = Table(
    TABLE_PREFIX + "chat_message", metadata,
    _pk(),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("role", String(16), nullable=False),
    Column("content", LongText, nullable=False),
    Column("kind", String(16), nullable=False, server_default="chat"),
    Column("meta", JsonText, nullable=True),
    Column("client_message_id", String(64), nullable=True),
    Column("turn_id", String(26), nullable=True),
    Column("interrupted", Boolean, nullable=False, server_default="0"),
    _now(),
    Column("deleted", Boolean, nullable=False, server_default="0"),
    Index("ca_ix_message_session_deleted_id", "session_id", "deleted", "id"),
    UniqueConstraint("session_id", "client_message_id", name="ca_uq_message_client_id"),
)

chat_turn = Table(
    TABLE_PREFIX + "chat_turn", metadata,
    Column("id", String(26), primary_key=True),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("state", String(16), nullable=False),
    Column("model", String(128), nullable=True),
    Column("prompt_version", String(32), nullable=True),
    Column("role_id", String(128), nullable=True),
    Column("skills", JsonText, nullable=True),
    Column("usage", JsonText, nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("started_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
    Index("ca_ix_turn_state_started", "state", "started_at"),
)

chat_queue = Table(
    TABLE_PREFIX + "chat_queue", metadata,
    _pk(),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("message_id", BigInteger, nullable=False),
    Column("client_message_id", String(64), nullable=True),
    Column("text", LongText, nullable=False),
    Column("attachments", JsonText, nullable=True),
    Column("status", String(16), nullable=False),
    Column("turn_id", String(26), nullable=True),
    Column("drain_attempts", Integer, nullable=False, server_default="0"),
    _now(),
    Index("ca_ix_queue_session_status_id", "session_id", "status", "id"),
)

upload = Table(
    TABLE_PREFIX + "upload", metadata,
    Column("id", String(26), primary_key=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("object_key", String(255), nullable=False),
    Column("mime", String(64), nullable=False),
    Column("size", BigInteger, nullable=False),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("referenced", Boolean, nullable=False, server_default="0"),
    _now(),
    Index("ca_ix_upload_owner", "owner_id"),
)

user_role = Table(
    TABLE_PREFIX + "user_role", metadata,  # 设计写作 role；MySQL 8 中 ROLE 是关键字，改用 user_role（见 T2 报告）
    _pk(),
    Column("public_id", String(40), nullable=False, unique=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("name", String(60), nullable=False),
    Column("tagline", String(120), nullable=False, server_default=""),
    Column("description", Text, nullable=False),
    Column("prompt", LongText, nullable=False),
    Column("locale", String(16), nullable=False, server_default="zh-CN"),
    _now(), _upd(),
    Column("deleted", Boolean, nullable=False, server_default="0"),
    Index("ca_ix_role_owner_deleted", "owner_id", "deleted"),
)

action_confirmation = Table(
    TABLE_PREFIX + "action_confirmation", metadata,
    Column("id", String(40), primary_key=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("session_id", BigInteger, nullable=False),
    Column("turn_id", String(26), nullable=True),
    Column("tool", String(64), nullable=False),
    Column("args", JsonText, nullable=True),  # 处理完 7 天后清空（O §10）
    Column("args_fingerprint", String(16), nullable=False),
    Column("title", String(120), nullable=False),
    Column("summary", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("decided_at", DateTime, nullable=True),
    _now(),
    Index("ca_ix_confirm_owner_status", "owner_id", "status"),
    Index("ca_ix_confirm_status_expires", "status", "expires_at"),
)

tool_call = Table(
    TABLE_PREFIX + "tool_call", metadata,
    _pk(),
    Column("turn_id", String(26), nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("tool", String(64), nullable=False),
    Column("permission", String(16), nullable=False),
    Column("args_fingerprint", String(16), nullable=False),
    Column("status", String(24), nullable=False),
    Column("latency_ms", Integer, nullable=True),
    Column("result_chars", Integer, nullable=True),
    _now(),
    Index("ca_ix_toolcall_turn", "turn_id"),
    Index("ca_ix_toolcall_created", "created_at"),
)

persona_profile = Table(
    TABLE_PREFIX + "persona_profile", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("app", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("markdown", LongText, nullable=False),
    Column("source", String(16), nullable=False),
    Column("generated_from", JsonText, nullable=True),
    _now(),
    UniqueConstraint("owner_id", "app", "version", name="ca_uq_persona_version"),
)

agent_job = Table(
    TABLE_PREFIX + "agent_job", metadata,
    _pk(),
    Column("kind", String(64), nullable=False),
    Column("payload", JsonText, nullable=True),
    Column("status", String(16), nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="5"),
    Column("run_after", DateTime, nullable=False),
    Column("lease_owner", String(64), nullable=True),
    Column("lease_until", DateTime, nullable=True),
    Column("dedupe_key", String(191), nullable=True),
    Column("last_error", Text, nullable=True),
    _now(), _upd(),
    Index("ca_ix_job_status_run_after", "status", "run_after"),
    UniqueConstraint("dedupe_key", name="ca_uq_job_dedupe"),
)

account_purge_log = Table(
    TABLE_PREFIX + "account_purge_log", metadata,
    _pk(),
    Column("user_hash", String(64), nullable=False),  # 不存原 user_id（O §3）
    Column("requested_at", DateTime, nullable=False),
    Column("finished_at", DateTime, nullable=True),
)

reminder = Table(
    TABLE_PREFIX + "reminder", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("session_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),
    Column("due_at", DateTime, nullable=False),           # UTC
    Column("timezone", String(64), nullable=False, server_default="UTC"),
    Column("content", Text, nullable=False),
    Column("status", String(16), nullable=False),         # pending | claimed | sent | cancelled | failed
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("lease_owner", String(64), nullable=True),
    Column("lease_until", DateTime, nullable=True),
    # 由确认执行创建：同一确认只建一条（重放、重复确认幂等）。
    Column("confirmation_id", String(40), nullable=True),
    Column("sent_turn_id", String(26), nullable=True),
    Column("last_error", Text, nullable=True),
    _now(), _upd(),
    Index("ca_ix_reminder_status_due", "status", "due_at"),
    Index("ca_ix_reminder_owner_status", "owner_id", "status"),
    UniqueConstraint("confirmation_id", name="ca_uq_reminder_confirmation"),
)
