"""表结构（D §3、O §2.1、O §10）。Alembic 迁移从这里生成 DDL，见 migrations/versions/。

方言可移植：目标库是 Postgres；MySQL 保留为兼容方言（历史测试库）。两处方言差异都收在本文件：
- ``LongText``：Postgres 用 TEXT，MySQL 用 MEDIUMTEXT（TEXT 只有 64KB）；
- ``JsonText``：Postgres 用 JSONB，MySQL 5.6 没有 JSON 类型，以 MEDIUMTEXT 存储并编解码。
"""

from datetime import UTC

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, Index, Integer, MetaData, String, Table, Text,
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


class UTCDateTime(types.TypeDecorator):
    """统一的时间列。

    为什么要包一层：以前用裸 ``DateTime``（Postgres 是 timestamp without time zone），
    读回来是「不带时区」的 datetime，和 ``datetime.now(UTC)`` 一比较就抛
    TypeError: can't compare offset-naive and offset-aware。全仓为此散落了 32 处
    ``replace(tzinfo=None)`` / ``replace(tzinfo=UTC)``，任何一处漏了就是一个 500。

    现在：Postgres 用 timestamptz（带时区），写入时保证带 UTC，读出来按 UTC 解释。
    MySQL 没有独立时区类型，仍存 DATETIME，但读写两侧都在这里统一按 UTC 处理。
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TIMESTAMP
            return dialect.type_descriptor(TIMESTAMP(timezone=True))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


# SQLite 只有 INTEGER PRIMARY KEY 才会自增；变体只影响 SQLite（测试用），Postgres 的 BIGSERIAL 不变。
_PK_TYPE = BigInteger().with_variant(Integer(), "sqlite")
_pk = lambda: Column("id", _PK_TYPE, primary_key=True, autoincrement=True)  # noqa: E731
_now = lambda: Column("created_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))  # noqa: E731
_upd = lambda: Column("updated_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())  # noqa: E731

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
    # 同一次提问的多个候选回复（左右滑动切换）：同组的助手消息 alt_group 相同（取第一条回复的消息 id），
    # 其中只有 alt_selected 为真的一条属于「当前对话」，其余候选不进历史、不进模型上下文。
    # 普通消息两列为空 / 真。
    Column("alt_group", BigInteger, nullable=True),
    Column("alt_selected", Boolean, nullable=False, server_default="1"),
    Index("ca_ix_message_session_deleted_id", "session_id", "deleted", "id"),
    Index("ca_ix_message_alt_group", "alt_group"),
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
    Column("started_at", UTCDateTime, nullable=True),
    Column("finished_at", UTCDateTime, nullable=True),
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
    Column("expires_at", UTCDateTime, nullable=False),
    Column("decided_at", UTCDateTime, nullable=True),
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
    Column("run_after", UTCDateTime, nullable=False),
    Column("lease_owner", String(64), nullable=True),
    Column("lease_until", UTCDateTime, nullable=True),
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
    Column("requested_at", UTCDateTime, nullable=False),
    Column("finished_at", UTCDateTime, nullable=True),
)

reminder = Table(
    TABLE_PREFIX + "reminder", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("session_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),
    Column("due_at", UTCDateTime, nullable=False),           # UTC
    Column("timezone", String(64), nullable=False, server_default="UTC"),
    Column("content", Text, nullable=False),
    Column("status", String(16), nullable=False),         # pending | claimed | sent | cancelled | failed
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("lease_owner", String(64), nullable=True),
    Column("lease_until", UTCDateTime, nullable=True),
    # 由确认执行创建：同一确认只建一条（重放、重复确认幂等）。
    Column("confirmation_id", String(40), nullable=True),
    Column("sent_turn_id", String(26), nullable=True),
    Column("last_error", Text, nullable=True),
    _now(), _upd(),
    Index("ca_ix_reminder_status_due", "status", "due_at"),
    Index("ca_ix_reminder_owner_status", "owner_id", "status"),
    UniqueConstraint("confirmation_id", name="ca_uq_reminder_confirmation"),
)


timeline_event = Table(
    TABLE_PREFIX + "timeline_event", metadata,
    _pk(),
    Column("public_id", String(26), nullable=False, unique=True),   # ULID，对外暴露
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),                 # 空串 = 用户级（记忆页手动添加）
    Column("session_id", BigInteger, nullable=True),
    Column("source_message_id", String(26), nullable=True),         # 由哪条用户消息得来；手动添加为空
    Column("origin", String(16), nullable=False),                   # tool | extracted | manual
    Column("kind", String(16), nullable=False),
    Column("title", String(60), nullable=False),
    Column("at_utc", UTCDateTime, nullable=False),
    Column("timezone", String(64), nullable=False, server_default="UTC"),
    Column("all_day", Boolean, nullable=False, server_default="0"),
    Column("recurrence", String(16), nullable=False, server_default="none"),
    Column("next_at_utc", UTCDateTime, nullable=True),                 # 按时间查用：一次性 = at，重复 = 下一次
    Column("status", String(16), nullable=False, server_default="scheduled"),
    Column("confidence", types.Float, nullable=False, server_default="1"),
    Column("reminder_id", BigInteger, nullable=True),
    Column("dedupe_key", String(64), nullable=False),
    _now(), _upd(),
    UniqueConstraint("owner_id", "role_id", "dedupe_key", name="ca_uq_timeline_dedupe"),
    Index("ca_ix_timeline_owner_role_next", "owner_id", "role_id", "status", "next_at_utc"),
    Index("ca_ix_timeline_source", "source_message_id"),
)


avatar_release = Table(
    TABLE_PREFIX + "avatar_release", metadata,
    _pk(),
    Column("avatar_key", String(64), nullable=False),               # 形象的稳定名，如 linche-spring
    Column("version", Integer, nullable=False),                      # 同一 avatar_key 下自增
    Column("name", String(60), nullable=False),
    Column("role_id", String(128), nullable=False, server_default=""),   # 空串 = 所有角色可用
    Column("status", String(16), nullable=False),                    # draft | online | offline
    Column("manifest", JsonText, nullable=False),
    Column("object_key", String(255), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("min_app_version", Integer, nullable=False, server_default="0"),
    Column("published_at", UTCDateTime, nullable=True),
    _now(), _upd(),
    UniqueConstraint("avatar_key", "version", name="ca_uq_avatar_version"),
    Index("ca_ix_avatar_status_role", "status", "role_id"),
)


persona_entry = Table(
    TABLE_PREFIX + "persona_entry", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),                  # 按「用户 + 角色」隔离，和记忆一致
    Column("topic", String(32), nullable=False),
    Column("memo", String(255), nullable=False),
    Column("section", String(8), nullable=False),                    # static | dynamic
    Column("is_inference", Boolean, nullable=False, server_default="0"),
    Column("confidence", types.Float, nullable=False, server_default="0.8"),
    Column("source_fact_ids", JsonText, nullable=True),              # 由哪些事实记忆归纳而来
    Column("mentioned_at", UTCDateTime, nullable=True),
    Column("happened_at", UTCDateTime, nullable=True),
    Column("superseded_by", BigInteger, nullable=True),              # 被哪条取代；空 = 当前有效
    Column("suppressed", Boolean, nullable=False, server_default="0"),   # 用户说「别再提」
    _now(), _upd(),
    Index("ca_ix_persona_owner_role", "owner_id", "role_id", "superseded_by"),
)

persona_cursor = Table(
    TABLE_PREFIX + "persona_cursor", metadata,
    Column("owner_id", BigInteger, primary_key=True),
    Column("role_id", String(128), primary_key=True),
    # 上次抽取处理到的位置：已处理的用户消息 id、待处理的累计字数（批量触发用，不每轮抽取）
    Column("last_message_id", BigInteger, nullable=False, server_default="0"),
    Column("pending_chars", Integer, nullable=False, server_default="0"),
    Column("updated_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)


user_consent = Table(
    TABLE_PREFIX + "user_consent", metadata,
    Column("owner_id", BigInteger, primary_key=True, autoincrement=False),
    # 训练用途单独同意：默认 False，必须用户明确打开。办法第 16 条一类要求不能捆绑在同意服务条款里。
    Column("training_consent", Boolean, nullable=False, server_default="0"),
    # 主动联系总开关。关闭后调度器不再发起主动回合（用户明确要求的提醒仍会发，那是对请求的兑现）。
    Column("proactive_enabled", Boolean, nullable=False, server_default="1"),
    Column("age_verified_adult", Boolean, nullable=False, server_default="0"),
    # 质检留存：同意后才保存对话与语音的原文（模型输入输出、识别文本、送去合成的文本）。
    # 默认关；不同意时 ca_llm_call / ca_voice_turn 仍记 token、耗时等不含内容的指标。
    Column("qa_retention", Boolean, nullable=False, server_default="0"),
    Column("updated_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

usage_span = Table(
    TABLE_PREFIX + "usage_span", metadata,
    Column("owner_id", BigInteger, primary_key=True, autoincrement=False),
    # 连续使用的起点与最近一次活跃。超过 30 分钟没有活跃就视为新的一段（与常见「连续使用」口径一致）。
    Column("started_at", UTCDateTime, nullable=False),
    Column("last_seen_at", UTCDateTime, nullable=False),
    Column("reminded_at", UTCDateTime, nullable=True),
    Column("updated_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)


# 「她主动找你」的用户偏好。原来在进程内（InMemoryPreferencesStore），重启就恢复默认：
# 用户以为自己关掉了主动消息，重启后又开始收到。
proactive_preferences = Table(
    TABLE_PREFIX + "proactive_prefs", metadata,
    Column("owner_id", BigInteger, primary_key=True, autoincrement=False),
    Column("events_enabled", Boolean, nullable=False, server_default="1"),
    Column("greetings_enabled", Boolean, nullable=False, server_default="0"),
    Column("call_enabled", Boolean, nullable=False, server_default="0"),
    Column("quiet_start", String(5), nullable=False, server_default="23:00"),
    Column("quiet_end", String(5), nullable=False, server_default="08:00"),
    Column("max_per_day", Integer, nullable=False, server_default="2"),
    Column("max_per_week", Integer, nullable=False, server_default="6"),
    Column("paused_until", UTCDateTime, nullable=True),
    Column("updated_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

# 应用内收件箱。原来在进程内且有 200 条上限、重启即丢：主动消息发出去、用户还没看到就没了。
# drained_at 非空 = 客户端已取走；未取走的按时间正序返回。
delivery_receipt = Table(
    TABLE_PREFIX + "delivery_receipt", metadata,
    Column("id", String(48), primary_key=True),
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=False),
    Column("text", LongText, nullable=False),
    Column("channel", String(16), nullable=False, server_default="in_app"),
    Column("meta", JsonText, nullable=True),
    Column("at", UTCDateTime, nullable=False),
    Column("drained_at", UTCDateTime, nullable=True),
    Column("created_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Index("ca_ix_receipt_owner_drained_at", "owner_id", "drained_at", "at"),
)

# 投递账本：频控（每天/每周几次）要跨重启、跨进程看「已经发过几次」。
# 原来在进程内，多 worker 各自计数，用户可能一天收到两倍的消息。
send_record = Table(
    TABLE_PREFIX + "send_record", metadata,
    _pk(),
    Column("owner_id", BigInteger, nullable=False),
    Column("at", UTCDateTime, nullable=False),
    Column("channel", String(16), nullable=False),
    Column("trigger", String(64), nullable=False, server_default=""),
    Index("ca_ix_send_owner_at", "owner_id", "at"),
)


# 每次模型调用一行。一个回合可能调用多次（工具往返、摘要），所以挂在 turn_id 下。
# 指标列（token、耗时、结束原因）永远写；内容列（输入输出、思考）只在用户同意质检留存时写，
# content_kept 记录这一行当时是否带了内容，清理与导出时据此区分。
llm_call = Table(
    TABLE_PREFIX + "llm_call", metadata,
    _pk(),
    Column("turn_id", String(26), nullable=False),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=True),
    Column("seq", Integer, nullable=False, server_default="0"),          # 回合内第几次调用
    Column("provider", String(64), nullable=True),
    Column("model", String(128), nullable=True),
    Column("prompt_version", String(32), nullable=True),
    Column("content_kept", Boolean, nullable=False, server_default="0"),
    Column("input_messages", JsonText, nullable=True),
    Column("output_text", LongText, nullable=True),
    Column("reasoning_text", LongText, nullable=True),
    Column("input_tokens", Integer, nullable=True),
    Column("output_tokens", Integer, nullable=True),
    Column("cached_tokens", Integer, nullable=True),
    Column("first_token_ms", Integer, nullable=True),
    Column("total_ms", Integer, nullable=True),
    Column("finish_reason", String(32), nullable=True),
    Column("error_code", String(64), nullable=True),
    Column("created_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Index("ca_ix_llmcall_turn", "turn_id"),
    Index("ca_ix_llmcall_owner_created", "owner_id", "created_at"),
    Index("ca_ix_llmcall_created", "created_at"),
)

# 每个语音回合一行：用户说的被识别成了什么、模型回了什么、送去合成的每一句、用的哪个声音。
# 判断 TTS 准不准需要“送进去的文本”和“出来的音频”两样；音频在对象存储里，这里只存键（可空）。
voice_turn = Table(
    TABLE_PREFIX + "voice_turn", metadata,
    _pk(),
    Column("turn_id", String(26), nullable=False),
    Column("session_id", BigInteger, nullable=False),
    Column("owner_id", BigInteger, nullable=False),
    Column("role_id", String(128), nullable=True),
    Column("user_message_id", BigInteger, nullable=True),                # 指向 kind=voice 的用户消息
    Column("content_kept", Boolean, nullable=False, server_default="0"),
    Column("stt_provider", String(64), nullable=True),
    Column("stt_text", LongText, nullable=True),
    Column("stt_confidence", Float, nullable=True),
    Column("llm_text", LongText, nullable=True),
    Column("tts_provider", String(64), nullable=True),
    Column("tts_voice", String(128), nullable=True),
    Column("tts_text", JsonText, nullable=True),                         # 送去合成的句子，JSON 数组
    Column("audio_in_key", String(255), nullable=True),
    Column("audio_out_key", String(255), nullable=True),
    Column("first_sentence_ms", Integer, nullable=True),                 # 从收到识别文本到第一句可朗读文本
    Column("total_ms", Integer, nullable=True),
    Column("interrupted", Boolean, nullable=False, server_default="0"),
    Column("created_at", UTCDateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Index("ca_ix_voiceturn_turn", "turn_id"),
    Index("ca_ix_voiceturn_owner_created", "owner_id", "created_at"),
    Index("ca_ix_voiceturn_created", "created_at"),
)
