"""`GET /admin/sessions/{id}/trace.jsonl`: NDJSON replay export of `jc_agent_trace`.

Calls `admin_export_session_trace` directly (same pattern `test_v1_mcp_contracts.py`
uses for MCP handlers) rather than through a `TestClient`, since `jc.main.app` eagerly
builds the real async engine on import and this environment has no MySQL driver
installed — exercising the endpoint function with a real SQLite-backed `AsyncSession`
covers the same code `Depends(get_db)` would have handed it.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import admin_export_session_trace
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
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_empty_session_exports_an_empty_body(db) -> None:
    response = await admin_export_session_trace(session_id="agsn_1", limit=5000, _=None, db=db)
    assert response.body == b""
    assert response.media_type == "application/x-ndjson"


@pytest.mark.asyncio
async def test_exports_one_json_line_per_event_in_seq_order(db) -> None:
    store = AgentTraceStore(db)
    await store.append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="system_prompt",
        role="system",
        payload={"text": "你是舟卡"},
        user_id="usr_1",
    )
    await store.append(
        trace_id_pk="agtr_2",
        session_id="agsn_1",
        event_type="user_message",
        role="user",
        payload={"text": "帮我优化简历"},
        user_id="usr_1",
    )
    await db.commit()

    response = await admin_export_session_trace(session_id="agsn_1", limit=5000, _=None, db=db)
    body = response.body.decode("utf-8")

    # Trailing newline, so the file is `wc -l`-friendly and `tail -1` lands on the
    # last real row rather than an empty string.
    assert body.endswith("\n")
    lines = body.strip("\n").split("\n")
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["seq"] == 0
    assert first["event_type"] == "system_prompt"
    assert first["payload"] == {"text": "你是舟卡"}
    assert second["seq"] == 1
    assert second["event_type"] == "user_message"
    assert second["user_id"] == "usr_1"


@pytest.mark.asyncio
async def test_long_payload_is_not_truncated_in_the_export(db) -> None:
    """The whole point of the underlying table: no UI-style character cut on export."""
    long_text = "思考内容" * 2000
    await AgentTraceStore(db).append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="reasoning",
        role="assistant",
        payload={"text": long_text},
    )
    await db.commit()

    response = await admin_export_session_trace(session_id="agsn_1", limit=5000, _=None, db=db)
    row = json.loads(response.body.decode("utf-8").strip("\n"))
    assert row["payload"]["text"] == long_text


@pytest.mark.asyncio
async def test_limit_caps_the_number_of_exported_rows(db) -> None:
    store = AgentTraceStore(db)
    for i in range(3):
        await store.append(
            trace_id_pk=f"agtr_{i}",
            session_id="agsn_1",
            event_type="user_message",
            role="user",
            payload={"text": f"turn {i}"},
        )
    await db.commit()

    response = await admin_export_session_trace(session_id="agsn_1", limit=2, _=None, db=db)
    lines = response.body.decode("utf-8").strip("\n").split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["seq"] == 0
    assert json.loads(lines[1])["seq"] == 1


@pytest.mark.asyncio
async def test_download_filename_carries_the_session_id(db) -> None:
    response = await admin_export_session_trace(session_id="agsn_1", limit=5000, _=None, db=db)
    assert response.headers["content-disposition"] == 'attachment; filename="agsn_1-trace.jsonl"'
