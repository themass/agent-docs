"""Audit lists carry the owning user's name, not just an opaque id.

An admin chasing a report has a person in hand, not a `usr_` id. Both audit lists
resolve the name through one batched query, and both must degrade to the raw id
rather than hiding a row when the user record is gone.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.api.admin_router import admin_list_llm_calls, admin_list_sessions
from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.llm_call import LlmCall
from jc.models.user import User, UserMeta
from jc.services.session_audit_service import SessionAuditService


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_named", email="named@example.com", password_hash="x"))
        session.add(UserMeta(user_id="usr_named", display_name="李国庆"))
        # No UserMeta row: a user who never set a display name still has an email,
        # which is the next most identifying thing an admin can act on.
        session.add(User(id="usr_bare", email="bare@example.com", password_hash="x"))
        session.add(
            AgentSession(id="agsn_named", user_id="usr_named", deerflow_thread_id="t1")
        )
        session.add(
            AgentSession(id="agsn_bare", user_id="usr_bare", deerflow_thread_id="t2")
        )
        session.add(
            AgentSession(id="agsn_ghost", user_id="usr_deleted", deerflow_thread_id="t3")
        )
        session.add(
            LlmCall(
                id="llm_1",
                user_id="usr_named",
                session_id="agsn_named",
                scenario="writer",
                caller="resume_elevator",
                channel="router",
                status="success",
            )
        )
        session.add(
            LlmCall(
                id="llm_system",
                user_id=None,
                scenario="ingest_fast",
                caller="profile_structurer",
                channel="router",
                status="success",
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_list_carries_display_name(db) -> None:
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search=None, _=None, audit=SessionAuditService(db)
    )
    by_id = {s.id: s for s in res.sessions}
    assert by_id["agsn_named"].user_display_name == "李国庆"
    assert by_id["agsn_named"].user_email == "named@example.com"


@pytest.mark.asyncio
async def test_session_list_falls_back_to_email_without_a_display_name(db) -> None:
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search=None, _=None, audit=SessionAuditService(db)
    )
    bare = next(s for s in res.sessions if s.id == "agsn_bare")
    assert bare.user_display_name is None
    assert bare.user_email == "bare@example.com"


@pytest.mark.asyncio
async def test_a_session_whose_user_is_gone_is_still_listed(db) -> None:
    """An audit view that hides records is worse than one showing an unresolved id."""
    res = await admin_list_sessions(
        limit=50, offset=0, user_id=None, search=None, _=None, audit=SessionAuditService(db)
    )
    ghost = next(s for s in res.sessions if s.id == "agsn_ghost")
    assert ghost.user_id == "usr_deleted"
    assert ghost.user_display_name is None
    assert ghost.user_email is None


@pytest.mark.asyncio
async def test_llm_call_list_carries_name_and_session(db) -> None:
    res = await admin_list_llm_calls(
        limit=50,
        offset=0,
        user_id=None,
        profile_id=None,
        scenario=None,
        caller=None,
        channel=None,
        status=None,
        trace_id=None,
        _=None,
        db=db,
    )
    call = next(c for c in res.calls if c.id == "llm_1")
    assert call.user_display_name == "李国庆"
    assert call.user_email == "named@example.com"
    # Already stored; the list view needs it to link a call to its event ledger.
    assert call.session_id == "agsn_named"


@pytest.mark.asyncio
async def test_a_call_with_no_user_reports_no_name(db) -> None:
    """Deterministic system scenarios run without a user and must not break the join."""
    res = await admin_list_llm_calls(
        limit=50,
        offset=0,
        user_id=None,
        profile_id=None,
        scenario=None,
        caller=None,
        channel=None,
        status=None,
        trace_id=None,
        _=None,
        db=db,
    )
    call = next(c for c in res.calls if c.id == "llm_system")
    assert call.user_id is None
    assert call.user_display_name is None
    assert call.user_email is None
