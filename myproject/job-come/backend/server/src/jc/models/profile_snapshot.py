"""Profile snapshot ledger — append-only history behind every `Profile.payload` write.

`Profile.version` is a plain optimistic-concurrency counter (see
`profile_patch_service.apply_confirmed_patch`'s compare-and-swap on it); the
previous `payload` is overwritten in the same `UPDATE` and nowhere kept. That
is correct for concurrency control and wrong for "the user wants last week's
version back" — there was no way to answer that question at all.

This table is the append-only fix, one row per payload transition: it holds
the payload as it stood *before* the write that produced `version_after`, so
row (version_after=N) is "what the profile looked like when it was version
N-1, right before it became N". Restoring to a past version means replaying
that row's `payload` back through the same confirm-gated patch path — never a
direct write to `Profile`, so a restore gets the same CAS safety and the same
audit trail as any other edit.

Captured by a single `before_flush` listener (`jc.db.profile_snapshot_hook`)
rather than by each of the seven call sites that mutate `Profile.payload`
(`profile_service`, `profile_patch_service`, `intake_service`,
`evidence_service`, `writing_options_service`): a per-call-site helper is one
`git grep` away from silently missing the next write path a future feature
adds. The hook inspects `Session.dirty`/`attributes.get_history` at flush
time, which sees every path by construction, including ones not written yet.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import JSONLongText


class ProfileSnapshot(Base, TimestampMixin):
    """One immutable pre-write copy of `Profile.payload`."""

    __tablename__ = "jc_profile_snapshot"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # No `index=True`: the composite unique index on (profile_id, version_after)
    # below already leads with profile_id, so a second single-column index
    # would only duplicate storage and write cost — same reasoning as
    # `jc_agent_trace.session_id`.
    profile_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jc_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The version this payload became *after* the write that triggered this
    # snapshot (i.e. `Profile.version` post-increment). Naming it by the
    # version it precedes, not the version it captures, keeps "restore to
    # version N" and "the snapshot row named N" pointing at the same row
    # without an off-by-one at the call site.
    version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # Who/what caused this write. Populated from the ambient LLM-call identity
    # (`jc.llm.call_context`) bound once per request by `api.deps.get_actor` —
    # the same ambient-identity mechanism `jc_llm_call` already relies on for
    # "the service three frames down does not have this argument".
    actor_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # agent_patch | manual_edit | intake | evidence | writing_options | confirm
    # | reopen — which write path produced this snapshot. Not a foreign key:
    # it is a label for operators reading the table, not a join target.
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    # The full payload as it stood immediately before this write. Never
    # truncated — restoring from a half-written snapshot would silently drop
    # resume content, which is the exact failure this table exists to prevent.
    payload: Mapped[dict] = mapped_column(JSONLongText, nullable=False)

    __table_args__ = (
        Index(
            "ix_jc_profile_snapshot_profile_version",
            "profile_id",
            "version_after",
            unique=True,
        ),
    )
