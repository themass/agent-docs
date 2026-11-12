"""The agent ledger: one row per event, one table, ordered and projected for the chat.

What these tests pin is the property the merge exists for — a tool call is stored
once, the chat reads it back, and the audit view still sees the full detail. They
also pin the two things that used to be wrong: the UI order is `seq` rather than a
`created_at` tie, and the user turn keeps both what was typed and what the model
received.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.agent.roles import default_role
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace
from jc.models.user import User
from jc.stores.agent_store import AgentStore
from jc.stores.agent_trace_store import AgentTraceStore


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/ledger.sqlite")

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


async def _append(maker, **kwargs) -> None:
    async with maker() as db:
        await AgentTraceStore(db).append(session_id="as1", **kwargs)
        await db.commit()


def _row(**kwargs) -> dict:
    """Defaults for one ledger event; callers override what the test is about."""
    base = {
        "trace_id_pk": "agtr_1",
        "event_type": "tool_call",
        "role": "assistant",
        "payload": {},
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
async def test_one_tool_call_is_one_row_and_the_chat_reads_it(maker):
    """The whole point: not one row for the UI and another for audit."""
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_tool",
            event_type="tool_call",
            ui_event="tool_start",
            payload={"name": "jc_profile_get", "arguments": {"section": "contact"}},
        ),
    )
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_result",
            event_type="tool_result",
            ui_event="tool_result",
            role="tool",
            content="已读取",
            payload={"name": "jc_profile_get", "result": "已读取"},
        ),
    )

    async with maker() as db:
        all_rows = await AgentTraceStore(db).list_for_session("as1")
        ui_rows = await AgentTraceStore(db).list_ui_for_session("as1")

    assert [r.event_type for r in all_rows] == ["tool_call", "tool_result"]
    # The same two rows, not a second copy: the chat filter only narrows the ledger.
    assert [r.id for r in ui_rows] == [r.id for r in all_rows]
    assert [r.seq for r in all_rows] == [0, 1]


@pytest.mark.asyncio
async def test_audit_only_rows_stay_out_of_the_chat(maker):
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_sys",
            event_type="system_prompt",
            role="system",
            payload={"text": "you are 舟卡"},
        ),
    )
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_user",
            event_type="user_message",
            ui_event="message",
            role="user",
            content="帮我看下简历",
            payload={"text": "…wrapped profile digest…\n帮我看下简历"},
        ),
    )

    async with maker() as db:
        ui_rows = await AgentTraceStore(db).list_ui_for_session("as1")
        audit_rows = await AgentTraceStore(db).list_for_session("as1")

    assert len(audit_rows) == 2
    assert [r.event_type for r in ui_rows] == ["user_message"]
    # Both halves of the user turn live on that one row: the transcript text the
    # user typed, and the wrapped input the model actually saw.
    assert ui_rows[0].content == "帮我看下简历"
    assert "wrapped profile digest" in ui_rows[0].payload["text"]


@pytest.mark.asyncio
async def test_the_chat_title_comes_from_the_first_visible_user_turn(maker):
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_a",
            event_type="user_message",
            ui_event="message",
            role="user",
            content="第一句",
            payload={},
        ),
    )
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_b",
            event_type="user_message",
            ui_event="message",
            role="user",
            content="第二句",
            payload={},
        ),
    )
    async with maker() as db:
        titles = await AgentTraceStore(db).first_ui_content(["as1"])
    assert titles == {"as1": "第一句"}


@pytest.mark.asyncio
async def test_message_count_only_counts_rows_a_user_would_see(maker):
    await _append(maker, **_row(trace_id_pk="s1", event_type="system_prompt",
                                role="system", payload={"text": "sys"}))
    await _append(maker, **_row(trace_id_pk="u1", event_type="user_message",
                                ui_event="message", role="user", content="hi", payload={}))
    await _append(maker, **_row(trace_id_pk="t1", event_type="tool_call",
                                ui_event="tool_start", payload={"name": "x"}))

    async with maker() as db:
        counts = await AgentStore(db).message_counts(["as1"])
    # Two visible rows out of three stored: the system prompt is audit only.
    assert counts == {"as1": 2}


@pytest.mark.asyncio
async def test_confirm_recovery_reads_the_ledger_not_a_client_payload(maker):
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_confirm",
            event_type="confirm",
            ui_event="confirm",
            payload={
                "confirm_id": "cfm_1",
                "profile_id": "p1",
                "patch": {"summary": "新"},
                "preview": {"version_before": 1},
            },
        ),
    )
    async with maker() as db:
        found = await AgentTraceStore(db).find_confirm("as1", "cfm_1")
        missing = await AgentTraceStore(db).find_confirm("as1", "cfm_other")

    assert found is not None and found.payload["patch"] == {"summary": "新"}
    assert missing is None


@pytest.mark.asyncio
async def test_a_decided_confirm_is_found_too_so_a_second_click_can_be_refused(maker):
    await _append(
        maker,
        **_row(
            trace_id_pk="agtr_applied",
            event_type="confirm_applied",
            ui_event="confirm_applied",
            payload={"confirm_id": "cfm_1", "status": "applied"},
        ),
    )
    async with maker() as db:
        found = await AgentTraceStore(db).find_confirm("as1", "cfm_1")
    assert found is not None and found.event_type == "confirm_applied"


@pytest.mark.asyncio
async def test_seq_is_monotonic_across_writers(maker):
    """Two events in the same millisecond must still replay in order."""
    for i in range(5):
        await _append(
            maker,
            **_row(trace_id_pk=f"agtr_{i}", event_type="reasoning",
                    ui_event="thinking", content=f"想 {i}", payload={"text": f"想 {i}"}),
        )
    async with maker() as db:
        rows = await AgentTraceStore(db).list_for_session("as1")
    assert [r.seq for r in rows] == [0, 1, 2, 3, 4]
    assert [r.content for r in rows] == ["想 0", "想 1", "想 2", "想 3", "想 4"]


def test_the_projection_table_is_gone_so_it_cannot_be_written_again():
    """A guard against re-introducing the duplicate store by accident."""
    assert AgentTrace.__tablename__ == "jc_agent_trace"
    assert "jc_agent_message" not in Base.metadata.tables
