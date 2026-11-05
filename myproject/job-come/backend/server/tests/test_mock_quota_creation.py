"""The quota is enforced where a session is created: a second full run in the month is refused and
leaves no session behind, warm-up is never refused, and a full run is recorded as counted."""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.exceptions import ForbiddenError
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.schemas.coach import MockSessionCreateRequest
from jc.services.interview_service import InterviewService

ACTOR = UserActor(user_id="free", session_id="s")


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/create.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(User(id="free", email="free@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(
            Profile(
                id="p1",
                user_id="free",
                owner_kind="user",
                payload={"contact": {"name": "A"}},
                version=1,
            )
        )
        await db.commit()
    yield maker
    await engine.dispose()


def _body(kind: str, **extra) -> MockSessionCreateRequest:
    # These tests are about the quota; the level is only here because creation requires one.
    return MockSessionCreateRequest(profile_id="p1", mode="warmup", kind=kind, level="mid", **extra)


async def _count(sessions) -> int:
    async with sessions() as db:
        return (await db.execute(select(func.count()).select_from(MockSession))).scalar_one()


@pytest.mark.asyncio
async def test_second_full_run_in_a_month_is_refused_and_leaves_no_session(sessions):
    async with sessions() as db:
        await InterviewService(db).create_mock_session(
            actor=ACTOR, body=_body("full")
        )
    assert await _count(sessions) == 1
    async with sessions() as db:
        with pytest.raises(ForbiddenError) as exc:
            await InterviewService(db).create_mock_session(
                actor=ACTOR,
                body=_body("full"),
            )
    assert exc.value.code == "mock_full_run_quota_exhausted"
    assert await _count(sessions) == 1, "a refused run must not leave a session behind"


@pytest.mark.asyncio
async def test_warmup_is_never_refused_even_after_the_full_run(sessions):
    async with sessions() as db:
        await InterviewService(db).create_mock_session(
            actor=ACTOR, body=_body("full")
        )
    async with sessions() as db:
        for _ in range(3):
            await InterviewService(db).create_mock_session(
                actor=ACTOR,
                body=_body("warmup"),
            )
    assert await _count(sessions) == 4


@pytest.mark.asyncio
async def test_a_full_run_is_recorded_as_counted_with_its_style(sessions):
    async with sessions() as db:
        created = await InterviewService(db).create_mock_session(
            actor=ACTOR,
            body=_body("full", style="pressure"),
        )
    async with sessions() as db:
        row = await db.get(MockSession, created.id)
    assert row.quota_counted is True
    assert row.style == "pressure"
