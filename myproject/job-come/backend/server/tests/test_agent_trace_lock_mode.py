"""The session lock must be `FOR NO KEY UPDATE`, never `FOR UPDATE`.

`AgentTraceStore.lock_session` is called from inside the agent's streaming loop and
holds until the next commit — potentially most of a turn. In PostgreSQL, an insert
into a child table takes `FOR KEY SHARE` on the referenced parent row, and
`FOR KEY SHARE` conflicts with exactly one mode: `FOR UPDATE`. So the API process
holding `FOR UPDATE` on the `jc_agent_session` row blocked the MCP subprocess from
inserting into `jc_profile_patch_confirm`, which has a foreign key to that session.

Measured on production: `jc_profile_patch` timed out at its 120 s client limit on
every attempt while `jc_profile_get` (no child insert) answered in under a second.
Reproduced deliberately — holding `FOR UPDATE` on the session row from a second
connection gave `baseline OK 4.4s` → `while-locked TIMEOUT >20s` → `after-release
OK 2.4s`.

`FOR NO KEY UPDATE` still serialises two concurrent sequence allocations, which is
the only thing `next_seq` needs, while being compatible with foreign-key checks.

These tests assert on the rendered SQL rather than on concurrency: a deadlock test
would need two processes and a real database to be meaningful, while the SQL is
what a future "simplification" back to `with_for_update()` would change.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace

SQLITE_SKIP = "PostgreSQL-only syntax; the lock mode does not exist in sqlite"


def _compiled(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).upper()


def test_session_lock_renders_no_key_update():
    """The exact statement `lock_session` issues."""
    sql = _compiled(
        select(AgentSession.id)
        .where(AgentSession.id == "s1")
        .with_for_update(key_share=True)
    )
    assert "FOR NO KEY UPDATE" in sql
    # `FOR UPDATE` is a prefix of `FOR NO KEY UPDATE`, so an unconditional
    # `"FOR UPDATE" in sql` check would pass on the broken version too.
    assert "FOR UPDATE" not in sql.replace("FOR NO KEY UPDATE", "")


def test_tail_lock_renders_no_key_update():
    """`next_seq`'s tail read takes the same mode, for the same reason."""
    sql = _compiled(
        select(AgentTrace.seq)
        .where(AgentTrace.session_id == "s1")
        .order_by(AgentTrace.seq.desc())
        .limit(1)
        .with_for_update(key_share=True)
    )
    assert "FOR NO KEY UPDATE" in sql
    assert "FOR UPDATE" not in sql.replace("FOR NO KEY UPDATE", "")


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, "FOR UPDATE"),
        ({"key_share": True}, "FOR NO KEY UPDATE"),
        ({"key_share": True, "read": False}, "FOR NO KEY UPDATE"),
        ({"read": True}, "FOR SHARE"),
    ],
)
def test_the_lock_modes_are_what_this_file_claims(kwargs, expected):
    """Pins the SQLAlchemy mapping itself, so the comment above stays true.

    Without this, an upgrade that changed which mode `key_share=True` renders
    would silently reintroduce the blocking while the other two tests kept passing
    on their own literal statements.
    """
    sql = _compiled(select(AgentSession.id).with_for_update(**kwargs))
    assert sql.rstrip().endswith(expected) or f" {expected}" in sql


def test_the_store_does_not_ask_for_the_blocking_mode():
    """Source-level guard: no bare `with_for_update()` in the trace store."""
    from pathlib import Path

    source = Path("src/jc/stores/agent_trace_store.py").read_text(encoding="utf-8")
    # Every call site must pass key_share=True explicitly.
    assert "with_for_update(key_share=True)" in source
    assert "with_for_update()" not in source
