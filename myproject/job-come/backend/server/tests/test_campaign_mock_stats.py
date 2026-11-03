"""Campaign progress counts finished mock interviews separately; the phase rule keeps its count."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.campaign_service import CampaignService

ACTOR = UserActor(user_id="alice", session_id="s")


@pytest.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/campaign_mock.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(User(id="alice", email="alice@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="alice", owner_kind="user", payload={}, version=1))
        for sid, status in [("m1", "completed"), ("m2", "active"), ("m3", "cancelled")]:
            db.add(MockSession(
                id=sid, profile_id="p1", user_id="alice", mode="target", question_ids=[],
                bank_draw_count=0, generated_count=0, status=status,
                started_at=datetime.now(UTC),
            ))
        await db.commit()
    yield maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_finished_mock_interviews_are_counted_apart_from_unfinished_ones(sessions):
    async with sessions() as db:
        stats = await CampaignService(db).get_stats("p1", actor=ACTOR)
    assert stats.progress["mock_completed"] == 1
    assert stats.progress["mock_sessions"] == 2, "the phase rule's count is unchanged"
