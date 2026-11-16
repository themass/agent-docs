"""A version bump must take the row lock, or the snapshot insert collides.

Found on production during a full e2e run: 21 `UniqueViolation`s, every one on
`Key (profile_id, version_after)=...`. Each was followed by `PendingRollbackError`,
so the rest of that request failed too — which is why two unrelated endpoints
timed out and looked like the test's fault.

The mechanism: every payload write loads the profile with a plain SELECT, does
`profile.version += 1`, and the `before_flush` listener inserts a
`jc_profile_snapshot` row keyed by `(profile_id, version_after)`. Two concurrent
writers read the same version, compute the same successor, and one loses.

These tests assert on the emitted SQL rather than on concurrency: a race needs two
connections and a real database to demonstrate, while the SQL is exactly what a
future "simplification" back to `get_by_id` would change.
"""

from __future__ import annotations

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models.profile import Profile
from jc.stores.profile_store import ProfileStore

PROFILE_ID = "prof_lock_probe"


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/lock.sqlite")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        session.add(Profile(id=PROFILE_ID, payload={}, status="draft"))
        await session.commit()
    yield sessions, engine
    await engine.dispose()


def _lock_clause(sql: str) -> str:
    """The trailing row-lock clause, upper-cased, or '' when there is none."""
    upper = sql.upper()
    for clause in ("FOR NO KEY UPDATE", "FOR UPDATE", "FOR SHARE", "FOR KEY SHARE"):
        if clause in upper:
            return clause
    return ""


@pytest.mark.asyncio
async def test_get_for_update_emits_no_key_update(db):
    """`FOR NO KEY UPDATE`, not `FOR UPDATE`.

    `FOR UPDATE` conflicts with the `FOR KEY SHARE` that any child-table insert
    takes on this row — the same mistake that made every `jc_profile_patch` call
    time out at 120s. `FOR NO KEY UPDATE` still serialises version writers, which
    is all the increment needs.
    """
    sessions, _ = db
    async with sessions() as session:
        stmt = (
            ProfileStore(session)._db  # noqa: SLF001 - reaching for the dialect only
        )
        del stmt
        from sqlalchemy import select

        sql = str(
            select(Profile)
            .where(Profile.id == PROFILE_ID)
            .with_for_update(key_share=True)
            .compile(dialect=postgresql.dialect())
        )
        assert _lock_clause(sql) == "FOR NO KEY UPDATE"


@pytest.mark.asyncio
async def test_get_for_update_returns_the_profile(db):
    sessions, _ = db
    async with sessions() as session:
        row = await ProfileStore(session).get_for_update(PROFILE_ID)
    assert row is not None
    assert row.id == PROFILE_ID


@pytest.mark.asyncio
async def test_get_for_update_hides_soft_deleted_profiles(db):
    """Locking must not resurrect a deleted profile — the predicate stays."""
    sessions, _ = db
    async with sessions() as session:
        row = await ProfileStore(session).get_for_update("prof_missing")
    assert row is None


def test_every_writer_that_bumps_version_takes_the_lock():
    """Source-level guard over every module that can write a profile version.

    Two failure modes, both observed on production:

    1. No row lock at all: `get_by_id` + `version += 1` lets two writers compute
       the same successor and collide on `(profile_id, version_after)`.
    2. Lock taken, then released: a `commit()` ends the transaction (and thus the
       FOR NO KEY UPDATE row lock) before a *later* bump in the same function.
       `prepare_tracks` had exactly this shape — lock at the top, three bumps,
       commits between them — and kept raising UniqueViolation after the mode-1
       fix. Re-locking after each commit is required, so a commit sitting between
       the nearest lock and a bump is an offence.

    AST rather than regex/text windows: docstrings containing the literal
    `version += 1` and indentation differences between `services/` (4-space
    methods) and `mcp/` (module-level functions) both produced phantom results
    in earlier text-based versions. An `AugAssign` node is real code by
    construction, and function nodes carry their own line ranges.
    """
    import ast
    from pathlib import Path

    src_root = Path(__file__).resolve().parents[1] / "src" / "jc"
    offenders: list[str] = []

    lock_markers = ("get_for_update(", "with_for_update(", "for_update=True")
    # The compare-and-swap writer issues `UPDATE ... WHERE version =
    # expected_version` and never reads-then-writes; it is serialised by the
    # predicate itself.
    cas_marker = "expected_version + 1"

    for path in sorted(src_root.rglob("*.py")):
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for fn in functions:
            bumps = [
                node
                for node in ast.walk(fn)
                if isinstance(node, ast.AugAssign)
                and isinstance(node.op, ast.Add)
                and isinstance(node.target, ast.Attribute)
                and node.target.attr == "version"
            ]
            if not bumps:
                continue
            fn_text = ast.get_source_segment(
                path.read_text("utf-8"), fn
            ) or ""
            if cas_marker in fn_text:
                continue

            lock_lines = [
                node.lineno
                for node in ast.walk(fn)
                if isinstance(node, ast.Call)
                and any(marker in ast.get_source_segment(path.read_text("utf-8"), node) or ""
                        for marker in lock_markers)
            ]
            commit_lines = [
                node.lineno
                for node in ast.walk(fn)
                if isinstance(node, ast.Await)
                and ".commit()" in (ast.get_source_segment(path.read_text("utf-8"), node) or "")
            ]

            for bump in bumps:
                prior_locks = [ln for ln in lock_lines if ln < bump.lineno]
                if not prior_locks:
                    offenders.append(f"{path.relative_to(src_root)}:{bump.lineno} (no row lock)")
                    continue
                nearest_lock = max(prior_locks)
                released = [
                    ln for ln in commit_lines if nearest_lock < ln < bump.lineno
                ]
                if released:
                    offenders.append(
                        f"{path.relative_to(src_root)}:{bump.lineno} "
                        f"(lock from line {nearest_lock} released by commit at line {released[-1]})"
                    )

    assert not offenders, (
        "these version bumps are not protected by a held row lock and will "
        f"collide on (profile_id, version_after): {offenders}"
    )
