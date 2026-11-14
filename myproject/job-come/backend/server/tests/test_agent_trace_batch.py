"""append_batch: one allocation, continuous seq, safe under concurrency."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.agent.roles import default_role
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace
from jc.models.user import User
from jc.stores.agent_trace_store import AgentTraceStore


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/batch.sqlite")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="test"))
        await db.flush()
        db.add(
            AgentSession(
                id="as1",
                user_id="u1",
                profile_id="p1",
                role_id=default_role().id,
                deerflow_thread_id="thr_1",
            )
        )
        await db.commit()
    yield sessions
    await engine.dispose()


def _item(pk: str, event_type: str = "token", **extra) -> dict:
    row = {
        "trace_id_pk": pk,
        "event_type": event_type,
        "role": "assistant",
        "payload": {"t": pk},
    }
    row.update(extra)
    return row


@pytest.mark.asyncio
async def test_two_batches_seq_strictly_increasing(maker):
    async with maker() as db:
        store = AgentTraceStore(db)
        await store.append_batch(
            [_item("a1"), _item("a2"), _item("a3")], session_id="as1"
        )
        await db.commit()
        await store.append_batch([_item("b1"), _item("b2")], session_id="as1")
        await db.commit()
        seqs = [
            r.seq
            for r in (
                await db.execute(
                    select(AgentTrace).where(AgentTrace.session_id == "as1").order_by(AgentTrace.seq)
                )
            ).scalars()
        ]
    assert seqs == [0, 1, 2, 3, 4]
    assert len(seqs) == len(set(seqs))


@pytest.mark.asyncio
async def test_explicit_seq_is_not_overwritten(maker):
    async with maker() as db:
        store = AgentTraceStore(db)
        await store.append_batch(
            [_item("e1", seq=7), _item("e2"), _item("e3", seq=99)],
            session_id="as1",
        )
        await db.commit()
        rows = list(
            (
                await db.execute(
                    select(AgentTrace).where(AgentTrace.session_id == "as1").order_by(AgentTrace.id)
                )
            ).scalars()
        )
    by_id = {r.id: r.seq for r in rows}
    assert by_id["e1"] == 7
    # start was allocated once (=0 here); offset 1 without explicit seq → 1
    assert by_id["e2"] == 1
    assert by_id["e3"] == 99


@pytest.mark.asyncio
async def test_empty_batch_does_not_advance_counter(maker):
    async with maker() as db:
        store = AgentTraceStore(db)
        assert await store.append_batch([], session_id="as1") == []
        await db.commit()
        rows = await store.append_batch([_item("first")], session_id="as1")
        await db.commit()
        assert rows[0].seq == 0


@pytest.mark.asyncio
async def test_concurrent_batches_unique_when_allocation_is_locked(maker, monkeypatch):
    """Two batches race; seq stays unique if next_seq is serialised (Postgres FOR UPDATE).

    SQLite's WITH FOR UPDATE does not serialise writers the way InnoDB/Postgres
    does — without an explicit lock both batches allocate start=0 and collide.
    The lock here stands in for the database row lock production relies on.
    """
    alloc_lock = asyncio.Lock()
    real_next = AgentTraceStore.next_seq

    async def locked_next(self, session_id: str) -> int:
        async with alloc_lock:
            return await real_next(self, session_id)

    monkeypatch.setattr(AgentTraceStore, "next_seq", locked_next)
    barrier = asyncio.Barrier(2)

    async def write_batch(prefix: str, n: int) -> list[int]:
        async with maker() as db:
            store = AgentTraceStore(db)
            await barrier.wait()
            items = [_item(f"{prefix}{i}") for i in range(n)]
            rows = await store.append_batch(items, session_id="as1")
            await db.commit()
            return [r.seq for r in rows]

    left, right = await asyncio.gather(write_batch("L", 5), write_batch("R", 5))
    all_seqs = left + right
    assert len(all_seqs) == 10
    assert len(set(all_seqs)) == 10
    assert sorted(all_seqs) == list(range(10))


@pytest.mark.asyncio
async def test_sqlite_without_row_lock_collides_on_concurrent_batches(maker):
    """Witness: on sqlite, concurrent append_batch can allocate the same start.

    Pins why production needs a real row lock — do not delete this if it fails.
    """
    barrier = asyncio.Barrier(2)

    async def write_batch(prefix: str, n: int):
        async with maker() as db:
            store = AgentTraceStore(db)
            await barrier.wait()
            items = [_item(f"{prefix}{i}") for i in range(n)]
            rows = await store.append_batch(items, session_id="as1")
            await db.commit()
            return [r.seq for r in rows]

    with pytest.raises(Exception) as ei:
        await asyncio.gather(write_batch("L", 5), write_batch("R", 5))
    assert "UNIQUE" in str(ei.value).upper() or "unique" in str(ei.value).lower()


@pytest.mark.asyncio
async def test_done_flush_lands_before_reader_sees_done_marker(maker):
    """Rows flushed in the batch that precedes a logical 'done' are readable.

    Mirrors the agent_service contract: append_batch + commit, then yield done.
    """
    async with maker() as db:
        store = AgentTraceStore(db)
        await store.append_batch(
            [
                _item("t1", event_type="token"),
                _item("t2", event_type="token"),
                _item("done1", event_type="done"),
            ],
            session_id="as1",
        )
        await db.commit()

    async with maker() as db:
        store = AgentTraceStore(db)
        rows = await store.list_for_session("as1")
        assert [r.event_type for r in rows] == ["token", "token", "done"]
        assert [r.seq for r in rows] == [0, 1, 2]
