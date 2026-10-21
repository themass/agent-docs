"""Capture a `ProfileSnapshot` row before every `Profile.payload` write.

Why a session-level hook instead of a call-site helper
-------------------------------------------------------
`Profile.payload` is mutated from seven places today (`profile_service`,
`profile_patch_service`, `intake_service`, `evidence_service`,
`writing_options_service`) and nothing stops an eighth appearing next sprint.
A helper each call site must remember to invoke is one missed call away from
a silent gap in the history — exactly the kind of thing that is only noticed
when a user asks to undo an edit that was never snapshotted. A `before_flush`
listener on `Session` sees every UPDATE to `Profile.payload` by construction,
including write paths that do not exist yet, so the guarantee holds without
being re-verified at every new call site.

Why `before_flush`, not a column trigger or an `after_update` listener
------------------------------------------------------------------------
`before_flush` runs inside the same `Session` and the same DB transaction
that is about to commit the `Profile` row, before the UPDATE is issued. It
can read `attributes.get_history(profile, "payload")` to recover the
pre-write value — the ORM has not overwritten it in memory yet, only in the
pending-changes bookkeeping — and it can `session.add()` a new
`ProfileSnapshot` row, which SQLAlchemy folds into the *same* flush/COMMIT.
That makes the snapshot atomic with the write it documents: either both land
or (on a rollback) neither does. An `after_update` listener fires per-row
after SQL has already been sent, which is too late to add more objects to
the same flush pass without a second round-trip; a DB trigger would work but
would move an application-level policy (which fields count as "changed",
what `source` label applies) into SQL, which is strictly harder to read,
test, and evolve with the rest of this codebase.

Why `payload` alone decides whether a snapshot is taken
---------------------------------------------------------
`version` is bumped by every one of the seven write paths exactly when
`payload` changes (see `Profile.version`'s docstring and every call site
above) — they are the same event already, by this codebase's own
convention. Watching `payload`'s attribute history is therefore sufficient
and avoids a second source of truth about "did this count as an edit".

Identity: ambient for the listener, explicit for the one call site that has it
--------------------------------------------------------------------------------
The `before_flush` listener has no argument list — it only sees whatever
SQLAlchemy hands a session-level event — so it has no choice but to read the
*user* from `jc.llm.call_context`'s ambient identity (bound once per request
by `api.deps.get_actor`, and once per agent turn by the harness adapter's
`_audit_context`). That is reused as-is; this module does not invent a
second "who" mechanism for the listener.

`build_snapshot`, by contrast, is called directly by `apply_confirmed_patch`,
which already holds `scope.user_id` as a plain argument — falling back to
the same ambient read there would make `actor_user_id` correct only by the
coincidence of whichever caller happens to sit under `get_actor`'s dependency
chain (true for the HTTP confirm route today, false for a test or script that
builds a `RunScope` directly and calls this function). `build_snapshot`
therefore takes `actor_user_id` as an explicit parameter instead.

The *source label* ("agent_patch" vs "manual_edit" vs "intake", ...) is a
different fact with a different lifetime: it is "which code path is mutating
the profile right now", which `jc.llm.call_context`'s `caller` field already
means something else for (the LLM-audit call site name, e.g.
"resume_service.elevate") and is not set at all on non-LLM write paths like
a plain profile edit. Repurposing it here would make a label on `jc_llm_call`
rows silently mean something different depending on which table is reading
it. This module therefore binds its own small ambient var
(`bind_snapshot_source`), scoped the same way, for exactly this one fact.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from agentkit.common.ids import new_id
from sqlalchemy import event
from sqlalchemy.orm import Session, attributes

from jc.models.profile import Profile
from jc.models.profile_snapshot import ProfileSnapshot

logger = logging.getLogger(__name__)

#: Default label when a write path has not called `bind_snapshot_source`.
#: Chosen so a future write path that forgets to bind one still produces a
#: usable (if generically-labelled) snapshot instead of losing it.
_DEFAULT_SOURCE = "manual_edit"
_source: ContextVar[str | None] = ContextVar("jc_profile_snapshot_source", default=None)


@contextmanager
def bind_snapshot_source(source: str) -> Any:
    """Label the `ProfileSnapshot.source` for every `Profile.payload` write in this block.

    Call sites bind this immediately before mutating `payload`, mirroring
    `jc.llm.call_context.llm_context_scope`'s "bind for one block, then
    restore" shape. Nesting restores the outer label on exit, so a helper
    that binds its own label and calls into code that already bound one
    higher up does not leak its label past its own scope.
    """
    token = _source.set(source)
    try:
        yield
    finally:
        _source.reset(token)


def _snapshot_source() -> str:
    return _source.get() or _DEFAULT_SOURCE


def _actor_user_id() -> str | None:
    # Imported here, not at module scope: `jc.models.__init__` imports this
    # module eagerly (see its own docstring) to register the listener below
    # as a side effect of `import jc.models`. `jc.llm.call_context` imports
    # `jc.llm.call_log`, which imports `jc.models.llm_call` — a submodule of
    # this same still-initializing package. A module-level import here would
    # make "import jc.llm before jc.models has finished" a circular import;
    # deferring it until the listener actually fires (well after both
    # packages are fully loaded) avoids depending on import order at all.
    from jc.llm.call_context import llm_context

    try:
        ctx = llm_context("profile_snapshot_hook")
    except Exception:  # noqa: BLE001
        return None
    return ctx.user_id


def build_snapshot(
    *, profile_id: str, version_after: int, payload: dict, actor_user_id: str | None
) -> ProfileSnapshot:
    """Construct a `ProfileSnapshot` row with the current ambient label and a caller-given actor.

    Public entry point for the one write path that cannot go through the
    `before_flush` listener below: `profile_patch_service.apply_confirmed_patch`
    issues a bare `UPDATE ... WHERE version = expected_version` for its
    compare-and-swap semantics, which never touches `Session.dirty` and so
    never triggers `_snapshot_dirty_profiles`. That call site snapshots
    explicitly with this function instead, inside the same
    `bind_snapshot_source` scope every other label uses for `source` -- but
    passes `actor_user_id` explicitly rather than reading the ambient
    identity, because the caller already has `RunScope.user_id` as a plain
    argument and that is the actual actor regardless of whether something
    upstream remembered to bind the ambient LLM-call identity first.
    """
    return ProfileSnapshot(
        id=new_id("pfsnap"),
        profile_id=profile_id,
        version_after=version_after,
        actor_user_id=actor_user_id,
        source=_snapshot_source(),
        payload=payload,
    )


@event.listens_for(Session, "before_flush")
def _snapshot_dirty_profiles(session: Session, _flush_context: object, _instances: object) -> None:
    """Add one `ProfileSnapshot` per `Profile` whose `payload` is about to change.

    Runs for every flush on every `Session` (this listener is registered on
    the base `Session` class, which `AsyncSession` delegates flushes to), so
    it is a no-op in the overwhelming majority of flushes that touch no
    `Profile` row -- `session.dirty` is typically empty or holds unrelated
    models, and the `isinstance` check below skips those immediately.
    """
    for obj in session.dirty:
        if not isinstance(obj, Profile):
            continue
        history = attributes.get_history(obj, "payload")
        if not history.deleted:
            # No prior value in the pending-changes history means `payload`
            # was not reassigned this flush (it may be dirty for an unrelated
            # column, e.g. `status` or `confirmed_at`) -- nothing to snapshot.
            continue
        previous_payload = history.deleted[0]
        # `version` is bumped by the same call site in the same flush, so its
        # *new* in-memory value is already `version_after` by the time this
        # listener runs -- no separate "peek at the value before increment"
        # is needed the way it was for `payload`.
        session.add(
            ProfileSnapshot(
                id=new_id("pfsnap"),
                profile_id=obj.id,
                version_after=obj.version,
                actor_user_id=_actor_user_id(),
                source=_snapshot_source(),
                payload=previous_payload,
            )
        )
