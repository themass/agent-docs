"""Application configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Model-call budgets below are sized from a measurement, not a guess.
#
# Benchmarked 2026-10-23 against the NewAPI gateway at gpt.sspacee.com, asking
# each model for the shape of output these pipelines actually produce (a long
# structured JSON, ~2.5-3k output tokens, from a ~2.6k-token input):
#
#     deepseek-v4-flash            16.3s   152 tok/s
#     gpt-5.6-luna                 21.0s   125 tok/s
#     deepseek-v4-pro              26.6s   117 tok/s
#     doubao-seed-2-0-pro-260215   56.5s    46 tok/s   (in no chain; do not add)
#
# Output length dominates: the same models answer a short question in 3-5s. So a
# per-attempt budget has to clear the *slowest useful* model's full generation,
# and the old 25s cleared none of them with margin — production logs showed the
# reviewer burning its whole 90s chain (two 25s timeouts plus overhead, median
# 59.9s, max 75.6s) and the writer falling back to `source_layout` twice, which
# is the unoptimised rule-based layout a user reads as "it did nothing".
#
# A too-short attempt budget is the worst of both: it pays for a generation it
# then throws away, and the failure surfaces as a fast, plausible-looking draft
# rather than an error. Hence 45s per attempt and 120s per chain, which leaves
# the writer 120/2.5 = 48s per hop — nearly 2x the slowest chain member's
# measured time. Worst-case preview is writer 120 + repair 40 = 160s, still
# inside the 240s SSE budget and the frontend's 255s watchdog.


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
        120, gt=0, le=120, alias="JC_PREVIEW_WRITER_TIMEOUT_SECONDS",
        description="Whole writer fallback-chain budget, not a per-model timeout",
    )
    jc_preview_repair_enabled: bool = Field(
        True,
        alias="JC_PREVIEW_REPAIR_ENABLED",
        description="One targeted rewrite when the generated draft measurably misses its blueprint",
    )
    jc_preview_repair_timeout_seconds: float = Field(
        40, gt=0, le=60, alias="JC_PREVIEW_REPAIR_TIMEOUT_SECONDS",
        description=(
            "Budget for the repair pass alone. Separate from the writer budget rather "
            "than carved out of it: the first pass writes the whole document."
        ),
    )
    jc_ingest_timeout_seconds: float = Field(
        120, gt=0, le=120, alias="JC_INGEST_TIMEOUT_SECONDS",
        description="Whole ingest deadline including local extraction and model failover",
    )
    jc_ingest_attempt_timeout_seconds: float = Field(
        45, gt=0, le=60, alias="JC_INGEST_ATTEMPT_TIMEOUT_SECONDS",
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

    # The one database this service has. Postgres only, and the driver must be
    # async: `postgresql+psycopg://user:pass@host:5432/job_come`. A bare
    # `postgresql://` resolves psycopg2, which cannot drive the async session.
    # Kept as a single URL rather than host/port/name/user/password parts: those
    # parts existed to assemble a MySQL URL and made the DSN the second place a
    # password could be written down.
    jc_database_url: str = Field("", alias="JC_DATABASE_URL")
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
    #: Prometheus /metrics. Off only when a deployment has no scraper; the
    #: endpoint costs a few microseconds per call and carries no user data.
    jc_metrics_enabled: bool = Field(True, alias="JC_METRICS_ENABLED")
    #: How this service names itself in the multi-service dashboard. Defaults to
    #: the `application` label already used on every series, so one setting does
    #: not have to be kept in two places.
    jc_metrics_service_name: str = Field("job-come", alias="JC_METRICS_SERVICE_NAME")
    #: How long one worker may answer from its in-memory session cache before
    #: asking Redis again. Bounds how long a logout can fail to take effect in a
    #: worker that missed the revocation broadcast; 60s is the backstop, not the
    #: expected window. 0 disables caching (one Redis round-trip per request).
    jc_session_cache_seconds: float = Field(60.0, ge=0, alias="JC_SESSION_CACHE_SECONDS")
    jc_session_cache_max_entries: int = Field(
        10_000, ge=0, alias="JC_SESSION_CACHE_MAX_ENTRIES"
    )
    #: Bounded queue between a finished model call and its audit row. Writes happen
    #: off the request path; when the queue is full the row is dropped rather than
    #: delaying the reply. 2000 covers a burst well past this deployment's traffic.
    jc_llm_log_queue_max: int = Field(2000, ge=1, alias="JC_LLM_LOG_QUEUE_MAX")
    #: Directory prometheus_client shares counters through when the backend runs
    #: more than one worker. Empty = per-process counters, which under a
    #: `--workers 2` service means a scrape reports exactly one worker's numbers
    #: and looks healthy while doing it. Set this whenever API_WORKERS > 1.
    jc_metrics_multiprocess_dir: str = Field(
        "", alias="JC_METRICS_MULTIPROCESS_DIR"
    )
    #: Other services whose `/metrics/snapshot` this admin panel may read, as
    #: `name=url` pairs separated by commas. The panel itself is a client, so the
    #: list has to live somewhere; the service that owns the panel is the natural
    #: place. A peer that is unreachable is reported as unreachable, never hidden.
    jc_metrics_peers: str = Field("", alias="JC_METRICS_PEERS")
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
    jc_agent_trace_retention_days: int = Field(
        60,
        ge=1,
        alias="JC_AGENT_TRACE_RETENTION_DAYS",
        description=(
            "How long one session's ledger (jc_agent_trace) is kept, enforced by "
            "scripts/prune_agent_trace.py. It holds full model input, so it is resume "
            "content: the window is a promise to the user, not an optimisation."
        ),
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
        200_000,
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
    # How often LangGraph persists graph state during one run. The default,
    # "async", writes a checkpoint plus a per-channel write set after *every*
    # graph step. Measured on production: 85 round-trips for a single turn, 55
    # of them writes at 360-550 ms each against a database 169 ms away — about
    # 25 s of pure database latency per turn, more than the model call itself.
    # "exit" writes once, when the graph exits.
    #
    # Safe here because JC's graph never calls LangGraph's `interrupt()`: the
    # HITL approval middleware is not installed, so no paused state needs
    # step-level durability. Verified against a real thread — a completed turn
    # and a turn abandoned mid-stream the way the stop button does it both
    # persist, and the following turn recalls the earlier codeword.
    jc_deerflow_checkpoint_durability: str = Field(
        "exit",
        alias="JC_DEERFLOW_CHECKPOINT_DURABILITY",
    )
    # Build the agent graphs at startup instead of on the first user turn. A cold
    # build costs 4-8 s and lands on whoever messages first after a deploy or a
    # restart. Off by default in tests (which build their own graphs) and on by
    # default everywhere else; see `prewarm_entry_clients`.
    jc_deerflow_prewarm: bool = Field(True, alias="JC_DEERFLOW_PREWARM")
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
        """LangGraph checkpointer DSN, matching ``jc_deerflow_checkpoint_backend``.

        Postgres takes an explicit URL. When that is empty the business database
        URL is reused: one database, one set of credentials, and no second copy of
        the password to rotate. The backend must agree with whatever this returns,
        so a `postgres` backend with no usable URL raises instead of quietly
        falling back to sqlite — a silent fallback is how conversation history
        ends up split across two stores that each look healthy.
        """
        backend = self.jc_deerflow_checkpoint_backend.lower()
        if backend == "postgres":
            url = self.jc_deerflow_checkpoint_postgres_url or self.jc_database_url
            if not url:
                raise ValueError(
                    "checkpointer backend is 'postgres' but neither "
                    "JC_DEERFLOW_CHECKPOINT_POSTGRES_URL nor a postgres JC_DATABASE_URL is set"
                )
            return url
        # A plain filesystem path, not a `sqlite://` URL: this value is handed to
        # DeerFlow's `resolve_sqlite_conn_str`, which resolves a path and rejects
        # `file:` URIs. A URL here would create a file literally named "sqlite:".
        path = Path(self.jc_deerflow_checkpoint_sqlite_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def database_url(self) -> str:
        """The one database URL. Postgres or nothing — there is no fallback.

        Raising here rather than defaulting is deliberate: a missing URL that
        silently resolved to `127.0.0.1:5432` would boot a service that looks
        healthy and can never write a row, which is worse than refusing to start.
        """
        url = self.jc_database_url.strip()
        if not url:
            raise ValueError(
                "JC_DATABASE_URL is required, e.g. "
                "postgresql+psycopg://user:pass@host:5432/job_come"
            )
        if not url.startswith(("postgresql+psycopg", "postgresql", "postgres")):
            raise ValueError(
                f"JC_DATABASE_URL must be a Postgres DSN, got scheme {url.split('://')[0]!r}. "
                "Expected postgresql+psycopg://"
            )
        return url

    @property
    def db_connect_args(self) -> dict[str, object]:
        """Driver-specific connect arguments for every engine we open.

        Without `connect_timeout` an unreachable host hangs for the OS TCP
        timeout and `alembic upgrade` looks like a silent hang instead of failing.

        Sessions are pinned to UTC. `server_default=func.now()` writes
        `CURRENT_TIMESTAMP`, which the server evaluates in the *session's* zone;
        this one runs Asia/Shanghai, so an unpinned session would stamp local time
        into columns every application writer fills with UTC.
        """
        return {
            "connect_timeout": self.jc_db_connect_timeout_seconds,
            "options": "-c timezone=UTC",
        }


settings = Settings()


# Settings are `extra="ignore"`, so a retired or misspelled JC_* name in .env is
# accepted in silence. That is fine for most of them, but a *model* name reads as
# authoritative: `JC_LLM_VISION_MODEL=qwen-vl-ocr` sat in a live .env looking like
# the setting that chose the OCR model, and editing it changed nothing — models
# are named only in routing.yaml (see the docstring in llm/chat_litellm.py for why
# the second source of truth was removed).
#
# Warn rather than raise: a stale line in a deployment's .env must not stop the
# service from booting.
_RETIRED_ENV = {
    "JC_LLM_VISION_MODEL": "改 backend/agent/llm/routing.yaml 的 vision 链",
    "JC_LLM_MODEL_FAST": "改 routing.yaml 的 flash / ingest_fast 链",
    "JC_LLM_MODEL_VISION": "改 routing.yaml 的 vision 链",
    "JC_LLM_MODEL_WRITER": "改 routing.yaml 的 writer 链",
    "JC_LLM_MODEL_COACH": "改 routing.yaml 的 coach 链",
}


def warn_retired_env() -> list[str]:
    """Report retired JC_* names present in the environment or .env file."""
    import os

    present: list[str] = []
    env_file = _PROJECT_ROOT / ".env"
    from_file: set[str] = set()
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                from_file.add(line.split("=", 1)[0].strip())
    for name, advice in _RETIRED_ENV.items():
        if name in os.environ or name in from_file:
            present.append(f"{name} 已停用，没有任何代码读取它；{advice}。")
    return present

