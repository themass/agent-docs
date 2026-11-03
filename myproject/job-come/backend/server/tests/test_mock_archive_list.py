"""The archive lists finished mock interviews of the profile, with whether each has a report, and
keeps them apart from real interviews."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.exceptions import ForbiddenError
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.interview_service import InterviewService

OWNER = UserActor(user_id="u1", session_id="s")
OTHER = UserActor(user_id="u2", session_id="s")
NOW = datetime.now(UTC)


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/archive.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        s.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await s.flush()
        s.add(Profile(id="p1", user_id="u1", owner_kind="user", payload={}, version=1))
        rows = [
            ("old", "completed", NOW - timedelta(days=2), {"ended_reason": "completed"}, None),
            ("new", "completed", NOW - timedelta(days=1), {"ended_reason": "user_ended",
                                                           "ended_early": True},
             {"questions": []}),
            ("live", "active", NOW, {}, None),
            ("void", "cancelled", NOW, {}, None),
        ]
        for sid, status, started, coverage, report in rows:
            s.add(MockSession(
                id=sid, profile_id="p1", user_id="u1", mode="target", style="gentle",
                question_ids=["q1"], bank_draw_count=0, generated_count=0, status=status,
                started_at=started.replace(tzinfo=None), coverage=coverage, report=report,
            ))
        await s.commit()
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_lists_only_finished_sessions_newest_first_with_report_flag(maker):
    async with maker() as s:
        out = await InterviewService(s).list_mock_sessions("p1", actor=OWNER)
    assert [item.id for item in out.mock_sessions] == ["new", "old"]
    new, old = out.mock_sessions
    assert new.has_report is True and new.ended_early is True and new.ended_reason == "user_ended"
    assert old.has_report is False and old.ended_early is False
    assert new.style == "gentle" and new.question_count == 1


@pytest.mark.asyncio
async def test_another_user_cannot_list_the_profile(maker):
    async with maker() as s:
        with pytest.raises(ForbiddenError):
            await InterviewService(s).list_mock_sessions("p1", actor=OTHER)
