"""The page's progress, skip and swap call the same guard the interviewer's tools use, behind the
session owner's check."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.exceptions import ForbiddenError
from jc.models.interview import InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import mock_guard_service
from jc.services.interview_service import InterviewService

OWNER = UserActor(user_id="u1", session_id="s")
OTHER = UserActor(user_id="u2", session_id="s")


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/actions.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        s.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await s.flush()
        s.add(Profile(id="p1", user_id="u1", owner_kind="user", payload={}, version=1))
        s.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲讲缓存设计",
                                question_type="behavioral"))
        s.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", question_ids=[],
            bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="deep",
        ))
        await s.commit()
    async with factory() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")
        await mock_guard_service.ask(scope, mock_session_id="ms1", question_id="q1")
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_progress_shows_the_question_on_the_table_and_the_swap_balance(maker):
    async with maker() as s:
        out = await InterviewService(s).mock_progress("ms1", actor=OWNER)
    assert out.current_question_id == "q1"
    assert out.swaps_left == 3 and out.style == "deep"


@pytest.mark.asyncio
async def test_skip_through_the_service_updates_progress(maker):
    async with maker() as s:
        out = await InterviewService(s).mock_action("ms1", actor=OWNER, action="skip",
                                                    question_id="q1")
    assert out.accepted is True
    async with maker() as s:
        progress = await InterviewService(s).mock_progress("ms1", actor=OWNER)
    assert progress.skipped == 1 and progress.current_question_id is None


@pytest.mark.asyncio
async def test_swap_refusal_comes_back_as_a_reason_not_an_error(maker):
    async with maker() as s:
        out = await InterviewService(s).mock_action("ms1", actor=OWNER, action="swap",
                                                    question_id="q-not-here")
    assert out.accepted is False and out.code == "not_current"


@pytest.mark.asyncio
async def test_another_user_cannot_act_on_the_session(maker):
    async with maker() as s:
        with pytest.raises(ForbiddenError):
            await InterviewService(s).mock_action("ms1", actor=OTHER, action="skip",
                                                  question_id="q1")
