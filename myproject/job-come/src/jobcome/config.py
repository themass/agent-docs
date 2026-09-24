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

    job_come_env: str = Field("development", alias="JOB_COME_ENV")
    job_come_api_prefix: str = Field("/api/v1", alias="JOB_COME_API_PREFIX")
    job_come_docs_enabled: bool = Field(True, alias="JOB_COME_DOCS_ENABLED")
    job_come_public_url: str = Field("http://127.0.0.1:3000", alias="JOB_COME_PUBLIC_URL")

    job_come_db_host: str = Field("127.0.0.1", alias="JOB_COME_DB_HOST")
    job_come_db_port: int = Field(3306, alias="JOB_COME_DB_PORT")
    job_come_db_name: str = Field("vpn", alias="JOB_COME_DB_NAME")
    job_come_db_user: str = Field("root", alias="JOB_COME_DB_USER")
    job_come_db_password: str = Field("", alias="JOB_COME_DB_PASSWORD")
    db_echo: bool = Field(False, alias="JOB_COME_DB_ECHO")

    job_come_redis_url: str = Field("redis://127.0.0.1:6379/0", alias="JOB_COME_REDIS_URL")

    job_come_cookie_secure: bool = Field(False, alias="JOB_COME_COOKIE_SECURE")
    job_come_session_ttl_days: int = Field(7, alias="JOB_COME_SESSION_TTL_DAYS")
    job_come_guest_ttl_days: int = Field(30, alias="JOB_COME_GUEST_TTL_DAYS")

    job_come_smtp_host: str = Field("", alias="JOB_COME_SMTP_HOST")
    job_come_smtp_port: int = Field(465, alias="JOB_COME_SMTP_PORT")
    job_come_smtp_user: str = Field("", alias="JOB_COME_SMTP_USER")
    job_come_smtp_password: str = Field("", alias="JOB_COME_SMTP_PASSWORD")
    job_come_smtp_use_ssl: bool = Field(True, alias="JOB_COME_SMTP_USE_SSL")
    job_come_email_from: str = Field("noreply@sspacee.com", alias="JOB_COME_EMAIL_FROM")
    job_come_password_reset_ttl_hours: int = Field(1, alias="JOB_COME_PASSWORD_RESET_TTL_HOURS")
    job_come_email_verify_ttl_hours: int = Field(48, alias="JOB_COME_EMAIL_VERIFY_TTL_HOURS")

    job_come_log_json: bool = Field(True, alias="JOB_COME_LOG_JSON")
    job_come_log_level: str = Field("INFO", alias="JOB_COME_LOG_LEVEL")
    job_come_llm_enabled: bool = Field(False, alias="JOB_COME_LLM_ENABLED")
    job_come_llm_model_fast: str = Field("jobcome-fast", alias="JOB_COME_LLM_MODEL_FAST")
    job_come_llm_model_vision: str = Field("jobcome-vision", alias="JOB_COME_LLM_MODEL_VISION")
    job_come_llm_routing_path: str = Field(
        "deploy/llm/routing.yaml",
        alias="JOB_COME_LLM_ROUTING_PATH",
    )
    job_come_skills_dir: str = Field("skills/public", alias="JOB_COME_SKILLS_DIR")
    openai_api_base: str = Field("http://127.0.0.1:4000/v1", alias="OPENAI_API_BASE")
    openai_api_key: str = Field("sk-litellm-local", alias="OPENAI_API_KEY")

    # Vision gateway (separate from text LLM; used by ingest Route C)
    yuai_vision_api_base: str = Field(
        "https://newapi.yuaiweiwu.com/v1",
        alias="YUAI_VISION_API_BASE",
    )
    yuai_vision_api_key: str = Field("", alias="YUAI_VISION_API_KEY")
    yuai_vision_model: str = Field("qwen-vl-ocr", alias="YUAI_VISION_MODEL")

    # Text LLM gateway (YuAI)
    yuai_api_base: str = Field("https://newapi.yuaiweiwu.com/v1", alias="YUAI_API_BASE")
    yuai_api_key: str = Field("", alias="YUAI_API_KEY")
    job_come_model_context_window: int = Field(
        200_000,
        alias="JOB_COME_MODEL_CONTEXT_WINDOW",
        description="Lead model context window (mt-gpt-5-6-terra / jobcome-coach)",
    )
    job_come_context_token_limit: int = Field(0, alias="JOB_COME_CONTEXT_TOKEN_LIMIT")
    job_come_summarization_trigger_ratio: float = Field(
        0.16,
        alias="JOB_COME_SUMMARIZATION_TRIGGER_RATIO",
        description="Compaction fires at this fraction of the model context window",
    )
    job_come_summarization_trigger_tokens: int = Field(
        0,
        alias="JOB_COME_SUMMARIZATION_TRIGGER_TOKENS",
        description="0 = auto (window × ratio, ~16% of 200K → 32K)",
    )
    job_come_summarization_keep_messages: int = Field(
        10,
        alias="JOB_COME_SUMMARIZATION_KEEP_MESSAGES",
    )
    job_come_debug_context_usage: bool = Field(False, alias="JOB_COME_DEBUG_CONTEXT_USAGE")
    job_come_admin_enabled: bool = Field(False, alias="JOB_COME_ADMIN_ENABLED")
    job_come_admin_token: str = Field("", alias="JOB_COME_ADMIN_TOKEN")

    # Object storage — Volcengine TOS (S3-compatible)
    job_come_s3_provider: str = Field("volcengine_tos", alias="JOB_COME_S3_PROVIDER")
    job_come_s3_endpoint: str = Field(
        "https://tos-s3-cn-beijing.volces.com",
        alias="JOB_COME_S3_ENDPOINT",
    )
    job_come_s3_bucket: str = Field("jobcome", alias="JOB_COME_S3_BUCKET")
    job_come_s3_region: str = Field("cn-beijing", alias="JOB_COME_S3_REGION")
    job_come_s3_access_key: str = Field("", alias="JOB_COME_S3_ACCESS_KEY")
    job_come_s3_secret_key: str = Field("", alias="JOB_COME_S3_SECRET_KEY")
    job_come_s3_force_path_style: bool = Field(False, alias="JOB_COME_S3_FORCE_PATH_STYLE")

    # CDN — user-facing download URLs (origin pull from TOS)
    job_come_cdn_domain: str = Field("https://files.job.sspacee.com", alias="JOB_COME_CDN_DOMAIN")
    job_come_cdn_sign_key: str = Field("", alias="JOB_COME_CDN_SIGN_KEY")
    job_come_download_url_ttl_sec: int = Field(900, alias="JOB_COME_DOWNLOAD_URL_TTL_SEC")
    job_come_storage_local_dir: str = Field(
        ".data/objects",
        alias="JOB_COME_STORAGE_LOCAL_DIR",
    )

    # DeerFlow harness (W5+); M1 dev uses local SQLite checkpoint file
    job_come_deerflow_checkpoint_backend: str = Field(
        "sqlite",
        alias="JOB_COME_DEERFLOW_CHECKPOINT_BACKEND",
    )
    job_come_deerflow_checkpoint_sqlite_path: str = Field(
        ".data/deerflow/checkpoints.sqlite3",
        alias="JOB_COME_DEERFLOW_CHECKPOINT_SQLITE_PATH",
    )
    job_come_deerflow_checkpoint_postgres_url: str = Field(
        "",
        alias="JOB_COME_DEERFLOW_CHECKPOINT_POSTGRES_URL",
    )
    job_come_deerflow_extensions_config: str = Field(
        "deploy/deerflow/extensions_config.json",
        alias="JOB_COME_DEERFLOW_EXTENSIONS_CONFIG",
    )
    job_come_deerflow_config_path: str = Field(
        "deploy/deerflow/config.yaml",
        alias="JOB_COME_DEERFLOW_CONFIG_PATH",
    )
    job_come_skills_root: str = Field("skills", alias="JOB_COME_SKILLS_ROOT")

    langfuse_public_key: str = Field("", alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field("", alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        "https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
    )

    @property
    def resolved_context_token_limit(self) -> int:
        if self.job_come_context_token_limit > 0:
            return self.job_come_context_token_limit
        return self.job_come_model_context_window

    @property
    def resolved_summarization_trigger_tokens(self) -> int:
        if self.job_come_summarization_trigger_tokens > 0:
            return self.job_come_summarization_trigger_tokens
        window = self.resolved_context_token_limit
        ratio = min(0.35, max(0.08, self.job_come_summarization_trigger_ratio))
        return max(4_096, int(window * ratio))

    @property
    def storage_remote_enabled(self) -> bool:
        return bool(self.job_come_s3_access_key and self.job_come_s3_secret_key)

    @property
    def deerflow_checkpoint_dsn(self) -> str:
        """LangGraph checkpointer DSN (sqlite file now; postgres later)."""
        backend = self.job_come_deerflow_checkpoint_backend.lower()
        if backend == "postgres":
            if not self.job_come_deerflow_checkpoint_postgres_url:
                raise ValueError("JOB_COME_DEERFLOW_CHECKPOINT_POSTGRES_URL is required")
            return self.job_come_deerflow_checkpoint_postgres_url
        path = Path(self.job_come_deerflow_checkpoint_sqlite_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"

    @property
    def database_url(self) -> str:
        user = quote_plus(self.job_come_db_user)
        password = quote_plus(self.job_come_db_password)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.job_come_db_host}:{self.job_come_db_port}/{self.job_come_db_name}"
            f"?charset=utf8mb4"
        )


settings = Settings()
