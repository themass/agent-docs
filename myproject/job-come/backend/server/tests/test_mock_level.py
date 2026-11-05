"""A mock session has a level: the user's choice, or the recommendation from the profile when the
request names none. With neither, creation is refused before anything is claimed or written."""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.exceptions import ConflictError
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.schemas.coach import MockSessionCreateRequest
from jc.services.interview_service import InterviewService

ACTOR = UserActor(user_id="u1", session_id="s")
FIVE_YEARS = {"experiences": [{"id": "e1", "company": "某公司", "title": "后端工程师",
                               "start_date": "2019-01", "end_date": "2024-01"}]}


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/level.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p_exp", user_id="u1", owner_kind="user", payload=FIVE_YEARS, version=1))
        db.add(Profile(id="p_empty", user_id="u1", owner_kind="user",
                       payload={"contact": {"name": "A"}}, version=1))
        await db.commit()
    yield makers
    await engine.dispose()


async def _create(maker, **body):
    async with maker() as db:
        return await InterviewService(db).create_mock_session(
            actor=ACTOR, body=MockSessionCreateRequest(mode="warmup", **body)
        )


async def _count(maker) -> int:
    async with maker() as db:
        return (await db.execute(select(func.count()).select_from(MockSession))).scalar_one()


@pytest.mark.asyncio
async def test_a_session_created_without_a_level_gets_the_recommended_one(maker):
    created = await _create(maker, profile_id="p_exp")
    assert created.level == "mid"
    async with maker() as db:
        stored = (await db.execute(select(MockSession))).scalar_one()
        assert stored.level == "mid"


@pytest.mark.asyncio
async def test_an_explicit_level_wins_over_the_recommendation(maker):
    created = await _create(maker, profile_id="p_exp", level="senior")
    assert created.level == "senior"


@pytest.mark.asyncio
async def test_no_level_and_no_recommendation_is_refused_and_leaves_nothing(maker):
    with pytest.raises(ConflictError) as exc:
        await _create(maker, profile_id="p_empty", kind="full")
    assert "请先选择面试级别" in str(exc.value)
    assert await _count(maker) == 0
    # A refused creation must not have claimed the month's full-run slot.
    created = await _create(maker, profile_id="p_empty", kind="full", level="junior")
    assert created.level == "junior"


@pytest.mark.asyncio
async def test_the_recommendation_endpoint_lists_all_four_levels_and_names_the_reason(maker):
    async with maker() as db:
        out = await InterviewService(db).level_recommendation("p_exp", actor=ACTOR)
    assert out.recommended == "mid" and out.years == 5.0
    assert "约 5 年" in out.reason
    assert [option.key for option in out.levels] == ["junior", "mid", "senior", "expert"]
    assert out.levels[1].benchmark == "P6" and out.levels[1].years == "3 到 6 年"


@pytest.mark.asyncio
async def test_a_profile_without_usable_dates_has_no_recommendation_but_still_lists_levels(maker):
    async with maker() as db:
        out = await InterviewService(db).level_recommendation("p_empty", actor=ACTOR)
    assert out.recommended is None and out.years is None and out.reason is None
    assert len(out.levels) == 4
