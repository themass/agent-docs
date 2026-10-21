"""AgentTraceStore: append-only session ledger, SQLite without remote resources."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.user import User
from jc.stores.agent_trace_store import AgentTraceStore


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_1", email="u@example.test", password_hash="x"))
        session.add(AgentSession(id="agsn_1", user_id="usr_1", deerflow_thread_id="thread_1"))
        session.add(AgentSession(id="agsn_2", user_id="usr_1", deerflow_thread_id="thread_2"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_session_with_no_rows_has_no_system_prompt(db) -> None:
    store = AgentTraceStore(db)
    assert await store.has_system_prompt("agsn_1") is False


@pytest.mark.asyncio
async def test_next_seq_starts_at_zero_and_increments(db) -> None:
    store = AgentTraceStore(db)
    assert await store.next_seq("agsn_1") == 0
    await store.append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="system_prompt",
        role="system",
        payload={"text": "你是舟卡"},
    )
    await db.commit()
    assert await store.next_seq("agsn_1") == 1
    assert await store.has_system_prompt("agsn_1") is True


@pytest.mark.asyncio
async def test_seq_is_independent_per_session(db) -> None:
    """Two sessions writing concurrently must not share a counter."""
    store = AgentTraceStore(db)
    await store.append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="system_prompt",
        role="system",
        payload={"text": "p1"},
    )
    await db.commit()

    # agsn_2 has written nothing yet, so its own next_seq must still be 0 —
    # not "1", which is what a session_id-blind counter would produce.
    assert await store.next_seq("agsn_2") == 0
    assert await store.has_system_prompt("agsn_2") is False


@pytest.mark.asyncio
async def test_list_for_session_replays_in_seq_order(db) -> None:
    store = AgentTraceStore(db)
    await store.append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="system_prompt",
        role="system",
        payload={"text": "p1"},
    )
    await store.append(
        trace_id_pk="agtr_2",
        session_id="agsn_1",
        event_type="user_message",
        role="user",
        payload={"text": "帮我优化简历"},
    )
    await store.append(
        trace_id_pk="agtr_3",
        session_id="agsn_1",
        event_type="assistant_message",
        role="assistant",
        payload={"text": "好的"},
    )
    await db.commit()

    rows = await store.list_for_session("agsn_1")
    assert [r.seq for r in rows] == [0, 1, 2]
    assert [r.event_type for r in rows] == ["system_prompt", "user_message", "assistant_message"]
    assert rows[1].payload == {"text": "帮我优化简历"}


@pytest.mark.asyncio
async def test_append_never_truncates_long_payload_text(db) -> None:
    """The whole point of this table: no 2000/4000-char cut like the UI event mapper."""
    store = AgentTraceStore(db)
    long_text = "思考内容" * 2000  # far past the 4000-char UI cut used for `thinking`
    await store.append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="reasoning",
        role="assistant",
        payload={"text": long_text},
    )
    await db.commit()

    rows = await store.list_for_session("agsn_1")
    assert rows[0].payload["text"] == long_text


@pytest.mark.asyncio
async def test_correlation_keys_round_trip(db) -> None:
    store = AgentTraceStore(db)
    await store.append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="tool_call",
        role="assistant",
        payload={"name": "jc_mock_session_history", "arguments": {"limit": 5}},
        user_id="usr_1",
        profile_id="prof_1",
        job_id="job_1",
        mock_session_id="mock_1",
        trace_id="trc_1",
        llm_call_id="llmc_1",
    )
    await db.commit()

    rows = await store.list_for_session("agsn_1")
    row = rows[0]
    assert row.user_id == "usr_1"
    assert row.profile_id == "prof_1"
    assert row.job_id == "job_1"
    assert row.mock_session_id == "mock_1"
    assert row.trace_id == "trc_1"
    assert row.llm_call_id == "llmc_1"


@pytest.mark.asyncio
async def test_sequence_follows_tail_not_row_count(db):
    store = AgentTraceStore(db)
    await store.append(trace_id_pk="gap", session_id="agsn_1", event_type="error",
                       role="assistant", payload={}, seq=12)
    await db.commit()
    assert await store.next_seq("agsn_1") == 13
