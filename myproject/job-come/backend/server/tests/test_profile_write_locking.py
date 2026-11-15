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
    """Source-level guard across all four services that do read-modify-write.

    Each of these did `get_by_id` + `version += 1` before this fix. A new writer
    added without the lock reintroduces the collision, and the failure shows up as
    an unrelated 500 rather than at the line that caused it.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "jc" / "services"
    offenders: list[str] = []

    for path in sorted(src.glob("*.py")):
        text = path.read_text("utf-8")
        if "version += 1" not in text:
            continue
        lines = text.splitlines()
        in_docstring = False
        for index, line in enumerate(lines, start=1):
            # Skip docstrings and comments: `profile_service._require_profile`
            # explains the rule in prose containing the literal `version += 1`,
            # and counting that as a write made this check report a phantom.
            stripped = line.strip()
            if stripped.count('"""') == 1:
                in_docstring = not in_docstring
                continue
            if in_docstring or stripped.startswith("#"):
                continue
            if "version += 1" not in line:
                continue
            # Look back to the start of the enclosing function, not a fixed number of
            # lines. A 40-line window missed `parse_stored_source` (load at 254, bump
            # at 338) and `prepare_tracks` (712 → 753) and reported both as unlocked
            # when they were already correct — the same "check the checker" trap as
            # the docstring false positive.
            start = 0
            for back in range(index - 1, -1, -1):
                line_back = lines[back - 1]
                if line_back.startswith("    async def ") or line_back.startswith("    def "):
                    start = back
                    break
            window = "\n".join(lines[start:index])
            locked = (
                "for_update=True" in window
                or "get_for_update(" in window
                or "with_for_update(" in window
                # The compare-and-swap writer does its own `WHERE version = ...`;
                # it never reads-then-writes.
                or "expected_version + 1" in window
            )
            if not locked:
                offenders.append(f"{path.name}:{index}")

    assert not offenders, (
        "these version bumps have no row lock above them and will collide on "
        f"(profile_id, version_after): {offenders}"
    )
