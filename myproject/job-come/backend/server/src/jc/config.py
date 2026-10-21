"""Application configuration."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jc_env: str = Field("development", alias="JC_ENV")
    jc_api_prefix: str = Field("/api/v1", alias="JC_API_PREFIX")
    jc_docs_enabled: bool = Field(True, alias="JC_DOCS_ENABLED")
    jc_preview_writer_timeout_seconds: float = Field(
        90, gt=0, le=120, alias="JC_PREVIEW_WRITER_TIMEOUT_SECONDS",
        description="Whole writer fallback-chain budget, not a per-model timeout",
    )
    jc_export_review_timeout_seconds: float = Field(
        90, gt=0, le=120, alias="JC_EXPORT_REVIEW_TIMEOUT_SECONDS"
    )
    jc_export_review_attempt_timeout_seconds: float = Field(
        25, gt=0, le=60, alias="JC_EXPORT_REVIEW_ATTEMPT_TIMEOUT_SECONDS",
        description="Per-model reviewer timeout within the shared total review budget",
    )
    jc_ingest_timeout_seconds: float = Field(
        90, gt=0, le=120, alias="JC_INGEST_TIMEOUT_SECONDS",
        description="Whole ingest deadline including local extraction and model failover",
    )
    jc_ingest_attempt_timeout_seconds: float = Field(
        25, gt=0, le=60, alias="JC_INGEST_ATTEMPT_TIMEOUT_SECONDS",
        description="Text connection/read-idle timeout; vision single-request timeout",
    )
    jc_ingest_stream_attempt_seconds: float = Field(
        30, gt=0, le=60, alias="JC_INGEST_STREAM_ATTEMPT_SECONDS",
        description="Complete structured-stream attempt cap, inside the shared ingest total budget",
    )
    jc_profile_parse_lease_seconds: int = Field(
        240, gt=30, le=3600, alias="JC_PROFILE_PARSE_LEASE_SECONDS",
        description=(
            "Database lease for one parse attempt; exceeds bounded storage and ingest budgets"
        ),
    )
    jc_profile_parse_concurrency: int = Field(
        2, ge=1, le=16, alias="JC_PROFILE_PARSE_CONCURRENCY",
        description="Maximum concurrent resume parses per API instance",
    )
    jc_public_url: str = Field("http://127.0.0.1:3000", alias="JC_PUBLIC_URL")

    jc_db_host: str = Field("127.0.0.1", alias="JC_DB_HOST")
    jc_db_port: int = Field(3306, alias="JC_DB_PORT")
    jc_db_name: str = Field("vpn", alias="JC_DB_NAME")
    jc_db_user: str = Field("root", alias="JC_DB_USER")
    jc_db_password: str = Field("", alias="JC_DB_PASSWORD")
    jc_db_connect_timeout_seconds: int = Field(10, alias="JC_DB_CONNECT_TIMEOUT_SECONDS")
    jc_db_pool_recycle_seconds: int = Field(900, alias="JC_DB_POOL_RECYCLE_SECONDS")
    jc_db_pool_timeout_seconds: int = Field(10, alias="JC_DB_POOL_TIMEOUT_SECONDS")
    db_echo: bool = Field(False, alias="JC_DB_ECHO")

    jc_redis_url: str = Field("redis://127.0.0.1:6379/0", alias="JC_REDIS_URL")
    jc_redis_key_prefix: str = Field(
        "jc:dev:",
        alias="JC_REDIS_KEY_PREFIX",
        description="All JC Redis keys must begin with this namespace.",
    )

    jc_cookie_secure: bool = Field(False, alias="JC_COOKIE_SECURE")
    jc_session_ttl_days: int = Field(7, alias="JC_SESSION_TTL_DAYS")
    jc_guest_ttl_days: int = Field(30, alias="JC_GUEST_TTL_DAYS")

    jc_smtp_host: str = Field("", alias="JC_SMTP_HOST")
    jc_smtp_port: int = Field(465, alias="JC_SMTP_PORT")
    jc_smtp_user: str = Field("", alias="JC_SMTP_USER")
    jc_smtp_password: str = Field("", alias="JC_SMTP_PASSWORD")
    jc_smtp_use_ssl: bool = Field(True, alias="JC_SMTP_USE_SSL")
    jc_email_from: str = Field("noreply@sspacee.com", alias="JC_EMAIL_FROM")
    jc_password_reset_ttl_hours: int = Field(1, alias="JC_PASSWORD_RESET_TTL_HOURS")
    jc_email_verify_ttl_hours: int = Field(48, alias="JC_EMAIL_VERIFY_TTL_HOURS")
    jc_email_verify_max_attempts: int = Field(5, alias="JC_EMAIL_VERIFY_MAX_ATTEMPTS")

    jc_log_json: bool = Field(True, alias="JC_LOG_JSON")
    jc_log_level: str = Field("INFO", alias="JC_LOG_LEVEL")
    jc_llm_enabled: bool = Field(False, alias="JC_LLM_ENABLED")
    jc_llm_routing_path: str = Field(
        "../agent/llm/routing.yaml",
        alias="JC_LLM_ROUTING_PATH",
    )

    # LLM call audit log (jc_llm_call / jc_llm_call_attempt).
    jc_llm_log_enabled: bool = Field(True, alias="JC_LLM_LOG_ENABLED")
    jc_llm_log_payload: bool = Field(
        True,
        alias="JC_LLM_LOG_PAYLOAD",
        description=(
            "Persist prompt/response/reasoning text. These contain resume personal data, "
            "so turning this off keeps metrics and failure codes without the content."
        ),
    )
    jc_llm_log_payload_max_chars: int = Field(
        60_000,
        alias="JC_LLM_LOG_PAYLOAD_MAX_CHARS",
        description="Per-column payload cap; longer text is truncated and flagged.",
    )
    jc_llm_log_retention_days: int = Field(
        90,
        alias="JC_LLM_LOG_RETENTION_DAYS",
        description="Audit window enforced by scripts/prune_llm_log.py.",
    )
    jc_skills_dir: str = Field("../agent/skills/public", alias="JC_SKILLS_DIR")

    # OpenAI-compatible LLM gateway (vendor-agnostic)
    jc_llm_api_base: str = Field("https://newapi.yuaiweiwu.com/v1", alias="JC_LLM_API_BASE")
    jc_llm_api_key: str = Field("", alias="JC_LLM_API_KEY")
    jc_llm_vision_api_base: str = Field(
        "https://newapi.yuaiweiwu.com/v1",
        alias="JC_LLM_VISION_API_BASE",
    )
    jc_llm_vision_api_key: str = Field("", alias="JC_LLM_VISION_API_KEY")
    jc_model_context_window: int = Field(
        200_000,
        alias="JC_MODEL_CONTEXT_WINDOW",
        description="Lead model context window (mt-gpt-5-6-terra / jc-coach)",
    )
    jc_context_token_limit: int = Field(0, alias="JC_CONTEXT_TOKEN_LIMIT")
    jc_summarization_trigger_ratio: float = Field(
        0.16,
        alias="JC_SUMMARIZATION_TRIGGER_RATIO",
        description="Compaction fires at this fraction of the model context window",
    )
    jc_summarization_trigger_tokens: int = Field(
        0,
        alias="JC_SUMMARIZATION_TRIGGER_TOKENS",
        description="0 = auto (window × ratio, ~16% of 200K → 32K)",
    )
    jc_summarization_keep_messages: int = Field(
        10,
        alias="JC_SUMMARIZATION_KEEP_MESSAGES",
    )
    jc_pii_redaction_enabled: bool = Field(
        False,
        alias="JC_PII_REDACTION_ENABLED",
        description=(
            "Deterministic PII redaction (email/phone/national id/credit card/"
            "api key) in model-bound requests, via DeerFlow's pii_redaction "
            "middleware. Raw values stay in the DB and UI; only what reaches "
            "the LLM and jc_llm_call payload capture is replaced with keyed "
            "placeholders. Does not redact names or employer names (those are "
            "not pattern-detectable)."
        ),
    )
    jc_pii_redaction_token_secret: str = Field(
        "",
        alias="JC_PII_REDACTION_TOKEN_SECRET",
        description=(
            "Deployment-scoped HMAC key for PII placeholder digests. Required "
            "(>=16 chars) when JC_PII_REDACTION_ENABLED=true; DeerFlow raises at "
            "config load otherwise."
        ),
    )
    jc_token_budget_enabled: bool = Field(
        True,
        alias="JC_TOKEN_BUDGET_ENABLED",
        description="Hard per-run token ceiling via DeerFlow's token_budget middleware.",
    )
    jc_token_budget_max_tokens: int = Field(
        150_000,
        alias="JC_TOKEN_BUDGET_MAX_TOKENS",
        description="Total input+output tokens allowed per agent run before a forced stop.",
    )
    jc_debug_context_usage: bool = Field(False, alias="JC_DEBUG_CONTEXT_USAGE")
    jc_admin_enabled: bool = Field(False, alias="JC_ADMIN_ENABLED")
    jc_admin_token: str = Field("", alias="JC_ADMIN_TOKEN")

    # Object storage — Volcengine TOS (S3-compatible)
    jc_s3_provider: str = Field("volcengine_tos", alias="JC_S3_PROVIDER")
    jc_s3_endpoint: str = Field(
        "https://tos-s3-cn-beijing.volces.com",
        alias="JC_S3_ENDPOINT",
    )
    jc_s3_bucket: str = Field("jc", alias="JC_S3_BUCKET")
    jc_s3_region: str = Field("cn-beijing", alias="JC_S3_REGION")
    jc_s3_access_key: str = Field("", alias="JC_S3_ACCESS_KEY")
    jc_s3_secret_key: str = Field("", alias="JC_S3_SECRET_KEY")
    jc_s3_force_path_style: bool = Field(False, alias="JC_S3_FORCE_PATH_STYLE")

    # CDN — user-facing download URLs (origin pull from TOS)
    jc_cdn_domain: str = Field("https://files.job.sspacee.com", alias="JC_CDN_DOMAIN")
    jc_cdn_sign_key: str = Field("", alias="JC_CDN_SIGN_KEY")
    jc_download_url_ttl_sec: int = Field(900, alias="JC_DOWNLOAD_URL_TTL_SEC")
    jc_storage_local_dir: str = Field(
        ".data/objects",
        alias="JC_STORAGE_LOCAL_DIR",
    )

    # DeerFlow harness (W5+); M1 dev uses local SQLite checkpoint file
    jc_deerflow_checkpoint_backend: str = Field(
        "sqlite",
        alias="JC_DEERFLOW_CHECKPOINT_BACKEND",
    )
    jc_deerflow_checkpoint_sqlite_path: str = Field(
        ".data/deerflow/checkpoints.sqlite3",
        alias="JC_DEERFLOW_CHECKPOINT_SQLITE_PATH",
    )
    jc_deerflow_checkpoint_postgres_url: str = Field(
        "",
        alias="JC_DEERFLOW_CHECKPOINT_POSTGRES_URL",
    )
    # All DeerFlow-generated state (skill projections, sessions, user views) lives
    # below .data, never in the legacy project-root .deer-flow directory.
    jc_deerflow_runtime_home: str = Field(
        ".data/deerflow/runtime",
        alias="JC_DEERFLOW_RUNTIME_HOME",
    )
    jc_deerflow_extensions_config: str = Field(
        "../agent/deerflow/extensions_config.json",
        alias="JC_DEERFLOW_EXTENSIONS_CONFIG",
    )
    jc_deerflow_config_path: str = Field(
        "../agent/deerflow/config.yaml",
        alias="JC_DEERFLOW_CONFIG_PATH",
    )
    jc_skills_root: str = Field("../agent/skills", alias="JC_SKILLS_ROOT")

    langfuse_public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field("", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        "https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )

    @property
    def resolved_context_token_limit(self) -> int:
        if self.jc_context_token_limit > 0:
            return self.jc_context_token_limit
        return self.jc_model_context_window

    @property
    def resolved_summarization_trigger_tokens(self) -> int:
        if self.jc_summarization_trigger_tokens > 0:
            return self.jc_summarization_trigger_tokens
        window = self.resolved_context_token_limit
        ratio = min(0.35, max(0.08, self.jc_summarization_trigger_ratio))
        return max(4_096, int(window * ratio))

    @property
    def storage_remote_enabled(self) -> bool:
        return bool(self.jc_s3_access_key and self.jc_s3_secret_key)

    @property
    def deerflow_checkpoint_dsn(self) -> str:
        """LangGraph checkpointer DSN (sqlite file now; postgres later)."""
        backend = self.jc_deerflow_checkpoint_backend.lower()
        if backend == "postgres":
            if not self.jc_deerflow_checkpoint_postgres_url:
                raise ValueError("JC_DEERFLOW_CHECKPOINT_POSTGRES_URL is required")
            return self.jc_deerflow_checkpoint_postgres_url
        path = Path(self.jc_deerflow_checkpoint_sqlite_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"

    @property
    def database_url(self) -> str:
        user = quote_plus(self.jc_db_user)
        password = quote_plus(self.jc_db_password)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.jc_db_host}:{self.jc_db_port}/{self.jc_db_name}"
            f"?charset=utf8mb4"
        )


settings = Settings()
