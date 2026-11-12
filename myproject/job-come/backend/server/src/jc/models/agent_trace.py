"""Agent ledger — the one record of what a session said, did and was told.

There used to be two tables. `jc_agent_message` held a curated subset of events
for the chat UI, `jc_agent_trace` held the full sequence for audit, and both were
written from the same stream loop. That made roughly half the bytes duplicates
(same tool call, same result, same reasoning, written twice) and gave the UI rows
no stable order — `created_at` alone ties within one transaction.

So there is one table now. Every row is one immutable event, ordered by
`(session_id, seq)`, carrying the full content in `payload`. Two columns decide
how a row is used:

- `event_type` is the canonical name, always set. It is what a replay, the
  reviewer and the report read.
- `ui_event` is set only when the chat UI renders this row, and names the widget
  (`message` / `thinking` / `tool_start` / `tool_result` / `usage` / `skill` /
  `confirm` / ...). Rows with `ui_event = NULL` exist for audit only — the system
  prompt and the wrapped model input are the two important ones.

`content` is the text the UI shows. `payload` is the full detail and is never
truncated: the trace is the only place that can answer "what exactly did the
model receive", so trimming it for storage would defeat its purpose. Anything the
UI needs beyond a string lives in `payload` under a key the projection reads.

Retention is bounded (60 days by default, see `scripts/prune_agent_log.py`),
which is why a plain `created_at` index is enough for the sweep.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import JSONLongText, LongText


class AgentTrace(Base, TimestampMixin):
    """One immutable event in a session's ledger."""

    __tablename__ = "jc_agent_trace"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # No `index=True`: the composite unique index on (session_id, seq) already
    # has session_id as its leading column.
    session_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jc_agent_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Monotonic per-session order, assigned by the writer under the session's
    # append lock. Not `created_at`: two events in the same millisecond must still
    # replay in a deterministic order.
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- correlation: the same identity keys `jc_llm_call` uses, so the two
    # tables join when a problem needs "what did this call cost" next to "what
    # did it actually send and receive". ---
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mock_session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: The `jc_llm_call` row this event belongs to, when the event came from one
    #: model call. Set for assistant/reasoning/tool rows of model turns.
    llm_call_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- what kind of event this row is (always set) ---
    # system_prompt | user_message | assistant_message | reasoning | tool_call |
    # tool_result | error | usage | skill | confirm | confirm_applied |
    # confirm_rejected | done
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The chat widget this row renders as, or NULL for audit-only rows. Kept
    #: beside `event_type` rather than derived in the reader: the UI vocabulary
    #: (`tool_start` vs `tool_call`) is a presentation choice, and putting it here
    #: means one mapping instead of two that can drift.
    ui_event: Mapped[str | None] = mapped_column(String(32), nullable=True)

    role: Mapped[str] = mapped_column(String(16), nullable=False)

    #: The text the chat UI shows for this row; NULL for structural events.
    content: Mapped[str | None] = mapped_column(LongText, nullable=True)

    #: Full event detail — model input, tool arguments, tool result, usage
    #: numbers, confirm card, traceback. Never truncated.
    payload: Mapped[dict] = mapped_column(JSONLongText, nullable=False)

    __table_args__ = (
        Index("ix_jc_agent_trace_session_seq", "session_id", "seq", unique=True),
        Index("ix_jc_agent_trace_user_created", "user_id", "created_at"),
        Index("ix_jc_agent_trace_trace_id", "trace_id"),
        # The chat list reads one session's UI rows in order; the retention sweep
        # walks `created_at`. Both are ordinary index work, cheap at this size.
        Index("ix_jc_agent_trace_session_ui", "session_id", "ui_event"),
        Index("ix_jc_agent_trace_created", "created_at"),
    )
