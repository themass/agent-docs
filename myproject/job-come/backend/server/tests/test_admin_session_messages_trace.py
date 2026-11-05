"""`GET /admin/sessions/{id}/messages` and `/trace`: inline JSON views over the
same two tables the Turn timeline and `trace.jsonl` export already read —
this is the "click a session, see its messages/trace without downloading a
file" admin UI path.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import admin_session_messages, admin_session_trace
from jc.db.base import Base
from jc.exceptions import NotFoundError
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.user import User
from jc.services.session_audit_service import SessionAuditService
from jc.stores.agent_message_store import AgentMessageStore
from jc.stores.agent_trace_store import AgentTraceStore


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_1", email="u@example.com", password_hash="x"))
        session.add(AgentSession(id="agsn_1", user_id="usr_1", deerflow_thread_id="thread_1"))
        await session.commit()
        yield session
    await engine.dispose()


def _audit(db):
    return SessionAuditService(db)


@pytest.mark.asyncio
async def test_messages_list_returns_rows_in_order(db) -> None:
    await AgentMessageStore(db).append(
        message_id="agmsg_1",
        session_id="agsn_1",
        role="user",
        event_type="message",
        content="帮我优化简历",
    )
    await AgentMessageStore(db).append(
        message_id="agmsg_2",
        session_id="agsn_1",
        role="assistant",
        event_type="message",
        content="好的",
        payload={"tool": "x"},
    )
    await db.commit()

    response = await admin_session_messages(
        session_id="agsn_1", limit=500, _=None, audit=_audit(db)
    )
    assert response.total == 2
    assert [m.id for m in response.messages] == ["agmsg_1", "agmsg_2"]
    assert response.messages[1].payload == {"tool": "x"}


@pytest.mark.asyncio
async def test_messages_list_missing_session_raises_not_found(db) -> None:
    with pytest.raises(NotFoundError):
        await admin_session_messages(session_id="agsn_missing", limit=500, _=None, audit=_audit(db))


@pytest.mark.asyncio
async def test_trace_list_returns_full_ledger_rows(db) -> None:
    await AgentTraceStore(db).append(
        trace_id_pk="agtr_1",
        session_id="agsn_1",
        event_type="system_prompt",
        role="system",
        payload={"text": "你是舟卡"},
    )
    await AgentTraceStore(db).append(
        trace_id_pk="agtr_2",
        session_id="agsn_1",
        event_type="user_message",
        role="user",
        payload={"text": "帮我优化简历"},
    )
    await db.commit()

    response = await admin_session_trace(session_id="agsn_1", limit=5000, _=None, audit=_audit(db))
    assert response.total == 2
    assert response.events[0].seq == 0
    assert response.events[0].event_type == "system_prompt"
    assert response.events[1].payload == {"text": "帮我优化简历"}


@pytest.mark.asyncio
async def test_trace_list_missing_session_raises_not_found(db) -> None:
    with pytest.raises(NotFoundError):
        await admin_session_trace(session_id="agsn_missing", limit=5000, _=None, audit=_audit(db))
