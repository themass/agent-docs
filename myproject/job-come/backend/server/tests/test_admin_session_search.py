"""`GET /admin/sessions?search=...` — match session id, thread id, or the
owning user's email. The three things an admin actually has in hand when
chasing one conversation down (a ticket quotes an email, a log line quotes
a session/thread id).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import admin_list_sessions
from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.user import User
from jc.services.session_audit_service import SessionAuditService


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_1", email="liguoqing@example.com", password_hash="x"))
        session.add(User(id="usr_2", email="other@example.com", password_hash="x"))
        session.add(
            AgentSession(id="agsn_alpha", user_id="usr_1", deerflow_thread_id="thread_alpha")
        )
        session.add(
            AgentSession(id="agsn_beta", user_id="usr_2", deerflow_thread_id="thread_beta")
        )
        await session.commit()
        yield session
    await engine.dispose()


def _audit(db):
    return SessionAuditService(db)


@pytest.mark.asyncio
async def test_search_matches_session_id(db) -> None:
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search="agsn_alpha", _=None, audit=_audit(db)
    )
    assert [s.id for s in res.sessions] == ["agsn_alpha"]


@pytest.mark.asyncio
async def test_search_matches_thread_id(db) -> None:
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search="thread_beta", _=None, audit=_audit(db)
    )
    assert [s.id for s in res.sessions] == ["agsn_beta"]


@pytest.mark.asyncio
async def test_search_matches_user_email(db) -> None:
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search="liguoqing", _=None, audit=_audit(db)
    )
    assert [s.id for s in res.sessions] == ["agsn_alpha"]


@pytest.mark.asyncio
async def test_no_search_returns_all(db) -> None:
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search=None, _=None, audit=_audit(db)
    )
    assert res.total == 2
