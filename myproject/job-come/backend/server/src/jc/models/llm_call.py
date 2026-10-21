"""LLM call audit log — one row per logical call, one row per endpoint attempt.

Two tables instead of one because a JC "call" is not a JC "HTTP request". The
router fails over across a scenario's endpoint chain, so a single business
operation can touch three models before it succeeds. Collapsing that into one
row loses exactly the question this log exists to answer: which model actually
produced the answer the user saw, and what did the ones before it do wrong.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import LongText


class LlmCall(Base, TimestampMixin):
    """One logical model call: a scenario resolved through its failover chain."""

    __tablename__ = "jc_llm_call"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    # --- who ---------------------------------------------------------------
    # Nullable: ingest runs for signed-out guests before an account exists.
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # --- what it was for ---------------------------------------------------
    profile_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The user's "分类": which routing scenario (writer / flash / vision / ...)
    # or, on the agent path, the harness model role.
    scenario: Mapped[str] = mapped_column(String(32), nullable=False)
    # Which code path asked. `resume_elevator`, `profile_structurer`, `agent` ...
    caller: Mapped[str] = mapped_column(String(64), nullable=False)
    # `router` for deterministic services, `harness` for the 舟卡 agent path.
    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="router")
    skill_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- outcome -----------------------------------------------------------
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # The model that actually produced the returned answer. Null when every
    # endpoint in the chain failed.
    final_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Stable reason code for the whole call (see call_log._error_code).
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Wall clock across the entire chain, including the failed attempts.
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- cost (summed over attempts) ---------------------------------------
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Micro-USD, integer: avoids float drift when summing a month of calls.
    cost_micro_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- correlation -------------------------------------------------------
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stream: Mapped[bool] = mapped_column(nullable=False, default=False)

    # --- payloads (only populated when JC_LLM_LOG_PAYLOAD is on) -----------
    # Resume text is personal data. These three columns are the only place in JC
    # that stores model payloads, they are gated by a single setting, and
    # `scripts/prune_llm_log.py` is what keeps retention bounded.
    prompt_text: Mapped[str | None] = mapped_column(LongText, nullable=True)
    response_text: Mapped[str | None] = mapped_column(LongText, nullable=True)
    reasoning_text: Mapped[str | None] = mapped_column(LongText, nullable=True)
    payload_truncated: Mapped[bool] = mapped_column(nullable=False, default=False)

    __table_args__ = (
        # "one user's behaviour", "one category's users", "this trace", "what is failing".
        Index("ix_jc_llm_call_user_created", "user_id", "created_at"),
        Index("ix_jc_llm_call_scenario_created", "scenario", "created_at"),
        Index("ix_jc_llm_call_profile_created", "profile_id", "created_at"),
        Index("ix_jc_llm_call_status_created", "status", "created_at"),
        Index("ix_jc_llm_call_trace", "trace_id"),
        Index("ix_jc_llm_call_created", "created_at"),
    )


class LlmCallAttempt(Base, TimestampMixin):
    """One endpoint attempt inside a call. Rows exist for failures too."""

    __tablename__ = "jc_llm_call_attempt"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # Deliberately not a ForeignKey: the attempt rows are written in the same
    # flush as the parent, and a cascade on a high-volume log table buys nothing
    # that `scripts/prune_llm_log.py` does not already do by call_id.
    call_id: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)

    model: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    api_base_env: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # True when the endpoint returned HTTP 200 but the response was unusable.
    # litellm counts these as successes; JC does not, and this column is how we
    # tell "the gateway is down" apart from "the model cannot hold the format".
    validator_failed: Mapped[bool] = mapped_column(nullable=False, default=False)

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_micro_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_jc_llm_call_attempt_call", "call_id", "attempt_index"),)
