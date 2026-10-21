"""AgentMessageStore persistence tests, using real SQLAlchemy without remote resources."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.user import User
from jc.stores.agent_message_store import AgentMessageStore


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_1", email="u@example.test", password_hash="x"))
        session.add(
            AgentSession(
                id="agsn_1",
                user_id="usr_1",
                deerflow_thread_id="thread_1",
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_session_with_no_messages_has_no_prior_user_turn(db) -> None:
    store = AgentMessageStore(db)
    assert await store.has_prior_user_message("agsn_1") is False


@pytest.mark.asyncio
async def test_the_first_appended_user_message_does_not_count_itself(db) -> None:
    """Mirrors `AgentService`: the flag must be read before the turn being sent is
    appended, or every turn sees itself and the pointer form never activates."""
    store = AgentMessageStore(db)
    before = await store.has_prior_user_message("agsn_1")
    await store.append(
        message_id="agm_1",
        session_id="agsn_1",
        role="user",
        event_type="message",
        content="第一轮",
    )
    await db.commit()

    assert before is False
    # But once committed, the *next* turn's check must see it.
    assert await store.has_prior_user_message("agsn_1") is True


@pytest.mark.asyncio
async def test_assistant_and_non_message_events_do_not_count_as_a_user_turn(db) -> None:
    store = AgentMessageStore(db)
    await store.append(
        message_id="agm_1",
        session_id="agsn_1",
        role="assistant",
        event_type="message",
        content="助手回复",
    )
    await store.append(
        message_id="agm_2",
        session_id="agsn_1",
        role="user",
        event_type="confirm_rejected",
        content=None,
    )
    await db.commit()

    assert await store.has_prior_user_message("agsn_1") is False


@pytest.mark.asyncio
async def test_a_second_session_is_not_affected_by_the_firsts_history(db) -> None:
    store = AgentMessageStore(db)
    await store.append(
        message_id="agm_1",
        session_id="agsn_1",
        role="user",
        event_type="message",
        content="第一轮",
    )
    await db.commit()
    db.add(
        AgentSession(id="agsn_2", user_id="usr_1", deerflow_thread_id="thread_2")
    )
    await db.commit()

    assert await store.has_prior_user_message("agsn_2") is False
