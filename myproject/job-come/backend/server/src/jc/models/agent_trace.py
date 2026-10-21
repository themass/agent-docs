"""Agent trace ledger — the SSOT for replaying one agent session end to end.

`jc_agent_message` is a UI projection (one row per thing the frontend needs
to render) and `jc_llm_call` / `jc_llm_call_attempt` are a cost/failover audit
(one row per model-call attempt). Neither can reconstruct the actual
system/user/assistant/tool message sequence DeerFlow sent and received for a
session, because neither stores the full content of every turn in order —
`jc_agent_message` only persists a curated subset of event types for the UI,
and `jc_llm_call`'s payload columns are single-turn and gated behind
`JC_LLM_LOG_PAYLOAD`.

This table is append-only: one row per immutable event, ordered by
(session_id, seq), typed payload carrying full content (never a truncated UI
summary). Concatenating all rows for a session and replaying them by seq
order reconstructs the complete conversation — the design mirrors naviforge's
TraceRecord ledger (see docs/myproject/naviforge/docs/MESSAGE_SYSTEM.md):
append-only events as the one source of truth, with any UI/audit view built
as a read-only projection over it rather than a second place that writes.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import JSONLongText


class AgentTrace(Base, TimestampMixin):
    """One immutable event in a session's full message ledger."""

    __tablename__ = "jc_agent_trace"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # No `index=True` here: the composite unique index on (session_id, seq)
    # below already has session_id as its leading column, so a second
    # single-column index on it would only duplicate storage and write cost.
    session_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jc_agent_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Monotonic per-session order, assigned by the writer under the session's
    # append lock. Not `created_at`: two events in the same millisecond must
    # still have a deterministic replay order, and MySQL timestamp precision
    # is not fine enough to guarantee that on its own.
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- correlation: same identity keys jc_llm_call uses, so the two tables
    # join cleanly when a problem needs "what did this call cost" (jc_llm_call)
    # next to "what did this call actually send and receive" (this table). ---
    # No `index=True`: the composite (user_id, created_at) index below has
    # user_id as its leading column, so this would be a duplicate.
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mock_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # No `index=True`: `Index("ix_jc_agent_trace_trace_id", "trace_id")` below
    # already covers it. `index=True` here would have generated the exact
    # same index name a second time -- MySQL/SQLite both reject that at
    # create-table time, which is what the original version of this column
    # did until this comment.
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    llm_call_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- what kind of event this row is ---
    # system_prompt | user_message | assistant_message | reasoning | tool_call |
    # tool_result | run_context | run_note | error | compaction
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    # Full content, shaped by event_type. Never truncated for storage — a UI
    # or export layer may choose to trim what it shows, but this table is the
    # one place that is not allowed to already be lossy.
    payload: Mapped[dict] = mapped_column(JSONLongText, nullable=False)

    # Multimodal pointers only (TOS URL + mime), never inline base64 — the
    # bytes already live in object storage via the same path jc_agent_message
    # uses for attachments; duplicating them here would make this table grow
    # the way jc_llm_call's payload columns were never allowed to.
    attachments: Mapped[list | None] = mapped_column(JSONLongText, nullable=True)

    __table_args__ = (
        Index("ix_jc_agent_trace_session_seq", "session_id", "seq", unique=True),
        Index("ix_jc_agent_trace_user_created", "user_id", "created_at"),
        Index("ix_jc_agent_trace_trace_id", "trace_id"),
    )
