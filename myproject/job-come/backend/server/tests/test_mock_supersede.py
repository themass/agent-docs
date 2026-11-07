"""A new round closes the running one of the same profile, and leaves every other profile alone.

Before this, a tab closed mid-interview left its session "active" for up to a day, and the next
round could not start while it stood (and the list kept showing it as running)."""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.schemas.coach import MockSessionCreateRequest
from jc.services.interview_service import InterviewService

ACTOR = UserActor(user_id="u1", session_id="s")


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/supersede.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        for pid in ("p1", "p2"):
            db.add(Profile(id=pid, user_id="u1", owner_kind="user",
                           payload={"contact": {"name": "A"}}, version=1))
        await db.commit()
    yield maker
    await engine.dispose()


def _body(profile_id: str = "p1") -> MockSessionCreateRequest:
    return MockSessionCreateRequest(profile_id=profile_id, mode="warmup", kind="warmup",
                                    level="mid")


async def _all(sessions) -> dict[str, MockSession]:
    async with sessions() as db:
        rows = (await db.execute(select(MockSession))).scalars().all()
        return {row.id: row for row in rows}


@pytest.mark.asyncio
async def test_a_new_round_ends_the_running_one_of_the_same_profile(sessions):
    async with sessions() as db:
        first = await InterviewService(db).create_mock_session(actor=ACTOR, body=_body())
    async with sessions() as db:
        second = await InterviewService(db).create_mock_session(actor=ACTOR, body=_body())
    rows = await _all(sessions)
    assert rows[first.id].status == "completed"
    assert (rows[first.id].coverage or {}).get("ended_reason") == "superseded"
    assert rows[second.id].status == "active"


@pytest.mark.asyncio
async def test_only_one_session_of_a_profile_is_ever_running(sessions):
    for _ in range(3):
        async with sessions() as db:
            await InterviewService(db).create_mock_session(actor=ACTOR, body=_body())
    rows = await _all(sessions)
    assert sum(1 for row in rows.values() if row.status == "active") == 1


@pytest.mark.asyncio
async def test_another_profiles_running_session_is_left_alone(sessions):
    async with sessions() as db:
        other = await InterviewService(db).create_mock_session(actor=ACTOR, body=_body("p2"))
    async with sessions() as db:
        await InterviewService(db).create_mock_session(actor=ACTOR, body=_body("p1"))
    assert (await _all(sessions))[other.id].status == "active"


@pytest.mark.asyncio
async def test_the_superseded_session_keeps_what_was_said(sessions):
    async with sessions() as db:
        first = await InterviewService(db).create_mock_session(actor=ACTOR, body=_body())
    async with sessions() as db:
        row = await db.get(MockSession, first.id)
        row.coverage = {
            "asked": [{"question_id": "q1", "kind": "main", "parent_question_id": None}]
        }
        await db.commit()
    async with sessions() as db:
        await InterviewService(db).create_mock_session(actor=ACTOR, body=_body())
    row = (await _all(sessions))[first.id]
    assert [a["question_id"] for a in row.coverage["asked"]] == ["q1"]
    assert (row.coverage or {}).get("ended_early") is True
