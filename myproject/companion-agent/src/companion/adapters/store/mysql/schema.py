"""MySQL 表结构（D §3、O §2.1、O §10）。Alembic 迁移从这里生成 DDL，见 migrations/versions/。"""

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Index, Integer, JSON, MetaData, String, Table, Text,
    UniqueConstraint, Column, func,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT

metadata = MetaData()

_pk = lambda: Column("id", BigInteger, primary_key=True, autoincrement=True)  # noqa: E731
_now = lambda: Column("created_at", DateTime, nullable=False, server_default=func.now())  # noqa: E731
_upd = lambda: Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())  # noqa: E731

chat_session = Table(
    "chat_session", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),
    Column("name", String(128), nullable=False, server_default=""),
    Column("locale", String(16), nullable=False, server_default="zh-CN"),
    _now(), _upd(),
    Column("deleted", Boolean, nullable=False, server_default="0"),
    Index("ix_session_owner_deleted_updated", "owner_id", "deleted", "updated_at"),
)

chat_message = Table(
    "chat_message", metadata,
    _pk(),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("role", String(16), nullable=False),
    Column("content", MEDIUMTEXT, nullable=False),
    Column("kind", String(16), nullable=False, server_default="chat"),
    Column("meta", JSON, nullable=True),
    Column("client_message_id", String(64), nullable=True),
    Column("turn_id", String(26), nullable=True),
    Column("interrupted", Boolean, nullable=False, server_default="0"),
    _now(),
    Column("deleted", Boolean, nullable=False, server_default="0"),
    Index("ix_message_session_deleted_id", "session_id", "deleted", "id"),
    UniqueConstraint("session_id", "client_message_id", name="uq_message_client_id"),
)

chat_turn = Table(
    "chat_turn", metadata,
    Column("id", String(26), primary_key=True),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("state", String(16), nullable=False),
    Column("model", String(128), nullable=True),
    Column("prompt_version", String(32), nullable=True),
    Column("role_id", String(128), nullable=True),
    Column("skills", JSON, nullable=True),
    Column("usage", JSON, nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("started_at", DateTime, nullable=True),
    Column("finished_at", DateTime, nullable=True),
    Index("ix_turn_state_started", "state", "started_at"),
)

chat_queue = Table(
    "chat_queue", metadata,
    _pk(),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("message_id", BigInteger, nullable=False),
    Column("client_message_id", String(64), nullable=True),
    Column("text", MEDIUMTEXT, nullable=False),
    Column("attachments", JSON, nullable=True),
    Column("status", String(16), nullable=False),
    Column("turn_id", String(26), nullable=True),
    Column("drain_attempts", Integer, nullable=False, server_default="0"),
    _now(),
    Index("ix_queue_session_status_id", "session_id", "status", "id"),
)

upload = Table(
    "upload", metadata,
    Column("id", String(26), primary_key=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("object_key", String(255), nullable=False),
    Column("mime", String(64), nullable=False),
    Column("size", BigInteger, nullable=False),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    Column("referenced", Boolean, nullable=False, server_default="0"),
    _now(),
    Index("ix_upload_owner", "owner_id"),
)

user_role = Table(
    "user_role", metadata,  # 设计写作 role；MySQL 8 中 ROLE 是关键字，改用 user_role（见 T2 报告）
    _pk(),
    Column("public_id", String(40), nullable=False, unique=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("name", String(60), nullable=False),
    Column("tagline", String(120), nullable=False, server_default=""),
    Column("description", Text, nullable=False),
    Column("prompt", MEDIUMTEXT, nullable=False),
    Column("locale", String(16), nullable=False, server_default="zh-CN"),
    _now(), _upd(),
    Column("deleted", Boolean, nullable=False, server_default="0"),
    Index("ix_role_owner_deleted", "owner_id", "deleted"),
)

action_confirmation = Table(
    "action_confirmation", metadata,
    Column("id", String(40), primary_key=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("session_id", BigInteger, nullable=False),
    Column("turn_id", String(26), nullable=True),
    Column("tool", String(64), nullable=False),
    Column("args", JSON, nullable=True),  # 处理完 7 天后清空（O §10）
    Column("args_fingerprint", String(16), nullable=False),
    Column("title", String(120), nullable=False),
    Column("summary", Text, nullable=False),
    Column("status", String(16), nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("decided_at", DateTime, nullable=True),
    _now(),
    Index("ix_confirm_owner_status", "owner_id", "status"),
    Index("ix_confirm_status_expires", "status", "expires_at"),
)

tool_call = Table(
    "tool_call", metadata,
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
    Index("ix_toolcall_turn", "turn_id"),
    Index("ix_toolcall_created", "created_at"),
)

persona_profile = Table(
    "persona_profile", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("app", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("markdown", MEDIUMTEXT, nullable=False),
    Column("source", String(16), nullable=False),
    Column("generated_from", JSON, nullable=True),
    _now(),
    UniqueConstraint("owner_id", "app", "version", name="uq_persona_version"),
)

agent_job = Table(
    "agent_job", metadata,
    _pk(),
    Column("kind", String(64), nullable=False),
    Column("payload", JSON, nullable=True),
    Column("status", String(16), nullable=False),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="5"),
    Column("run_after", DateTime, nullable=False),
    Column("lease_owner", String(64), nullable=True),
    Column("lease_until", DateTime, nullable=True),
    Column("dedupe_key", String(191), nullable=True),
    Column("last_error", Text, nullable=True),
    _now(), _upd(),
    Index("ix_job_status_run_after", "status", "run_after"),
    UniqueConstraint("dedupe_key", name="uq_job_dedupe"),
)

account_purge_log = Table(
    "account_purge_log", metadata,
    _pk(),
    Column("user_hash", String(64), nullable=False),  # 不存原 user_id（O §3）
    Column("requested_at", DateTime, nullable=False),
    Column("finished_at", DateTime, nullable=True),
)
