"""ProfileSnapshot hook: before_flush capture + the CAS path's explicit build_snapshot.

SQLite without remote resources, mirroring `test_agent_trace_store.py`'s fixture shape.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.db.profile_snapshot_hook import bind_snapshot_source, build_snapshot
from jc.llm.call_context import bind_llm_context, clear_llm_context
from jc.models import *  # noqa: F403
from jc.models.profile import Profile
from jc.models.profile_snapshot import ProfileSnapshot
from jc.models.user import User


@pytest.fixture(autouse=True)
def _clear_llm_identity():
    clear_llm_context()
    yield
    clear_llm_context()


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_1", email="u@example.test", password_hash="x"))
        session.add(
            Profile(
                id="prof_1",
                user_id="usr_1",
                owner_kind="user",
                version=1,
                payload={"summary": "v1"},
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


async def _profile(db) -> Profile:
    return (await db.execute(select(Profile).where(Profile.id == "prof_1"))).scalar_one()


async def _snapshots(db) -> list[ProfileSnapshot]:
    stmt = (
        select(ProfileSnapshot)
        .where(ProfileSnapshot.profile_id == "prof_1")
        .order_by(ProfileSnapshot.version_after.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


@pytest.mark.asyncio
async def test_plain_orm_write_captures_pre_write_payload(db) -> None:
    """Simulates `profile_service.update`: direct attribute assignment + commit."""
    profile = await _profile(db)
    bind_llm_context(user_id="usr_1")
    with bind_snapshot_source("manual_edit"):
        profile.payload = {"summary": "v2"}
        profile.version = 2
        await db.commit()

    rows = await _snapshots(db)
    assert len(rows) == 1
    assert rows[0].version_after == 2
    assert rows[0].payload == {"summary": "v1"}  # the OLD value, not v2
    assert rows[0].source == "manual_edit"
    assert rows[0].actor_user_id == "usr_1"


@pytest.mark.asyncio
async def test_multiple_sequential_writes_produce_multiple_rows(db) -> None:
    profile = await _profile(db)
    with bind_snapshot_source("intake"):
        profile.payload = {"summary": "v2"}
        profile.version = 2
        await db.commit()

    profile = await _profile(db)
    with bind_snapshot_source("evidence"):
        profile.payload = {"summary": "v3"}
        profile.version = 3
        await db.commit()

    rows = await _snapshots(db)
    assert [r.version_after for r in rows] == [2, 3]
    assert [r.payload["summary"] for r in rows] == ["v1", "v2"]
    assert [r.source for r in rows] == ["intake", "evidence"]
    # Composite unique index (profile_id, version_after) must not collide.
    assert len({(r.profile_id, r.version_after) for r in rows}) == 2


@pytest.mark.asyncio
async def test_unrelated_column_change_does_not_snapshot(db) -> None:
    """Changing `status` without touching `payload` must not produce a row."""
    profile = await _profile(db)
    profile.status = "confirmed"
    await db.commit()

    rows = await _snapshots(db)
    assert rows == []


@pytest.mark.asyncio
async def test_build_snapshot_matches_before_flush_shape(db) -> None:
    """The CAS path's explicit constructor must produce the same row shape.

    `actor_user_id` is passed explicitly here (mirroring `scope.user_id` at
    the real call site), not read from ambient `jc.llm.call_context` state —
    see `build_snapshot`'s docstring for why the CAS path cannot rely on the
    ambient identity having been bound by something upstream.
    """
    with bind_snapshot_source("agent_patch"):
        snap = build_snapshot(
            profile_id="prof_1",
            version_after=5,
            payload={"summary": "old"},
            actor_user_id="usr_1",
        )
    db.add(snap)
    await db.commit()

    rows = await _snapshots(db)
    assert len(rows) == 1
    assert rows[0].version_after == 5
    assert rows[0].payload == {"summary": "old"}
    assert rows[0].source == "agent_patch"
    assert rows[0].actor_user_id == "usr_1"


@pytest.mark.asyncio
async def test_default_source_label_when_unbound(db) -> None:
    """A write path that forgets to bind a label still gets a usable row."""
    profile = await _profile(db)
    profile.payload = {"summary": "v2"}
    profile.version = 2
    await db.commit()

    rows = await _snapshots(db)
    assert len(rows) == 1
    assert rows[0].source == "manual_edit"  # _DEFAULT_SOURCE
