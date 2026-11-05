"""An answer belongs to the mock session it was given in.

A bank question is reused across sessions. Reading "the latest answer to this question" without the
session showed an earlier session's answer in a new session's transcript, and made a question that
had not been answered here look answered."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.mock_guard_service import plan
from jc.services.mock_report_service import session_transcript
from jc.stores.interview_store import InterviewStore

OTHER_SESSION_ANSWER = "上一场里我讲过拆表的事。"


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/scope.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user",
                            payload={"experience": "结算接口拆表"}, version=1))
        session.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲一个你拆分数据的经历",
                                      question_type="behavioral"))
        for session_id, asked in (
            ("ms1", [{"question_id": "q1", "kind": "main", "parent_question_id": None}]),
            ("ms2", []),
        ):
            session.add(MockSession(
                id=session_id, profile_id="p1", user_id="u1", mode="target",
                question_ids=["q1"] if asked else [], bank_draw_count=0, generated_count=0,
                status="active", started_at=datetime.now(UTC), style="standard",
                coverage={"asked": asked},
            ))
        session.add(AnswerAttempt(id="a2", question_id="q1", profile_id="p1",
                                  mock_session_id="ms2", user_answer=OTHER_SESSION_ANSWER,
                                  coach_feedback={}, reference_answer=None))
        await session.commit()
    yield maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_an_answer_from_another_session_is_not_this_sessions_answer(db):
    async with db() as s:
        store = InterviewStore(s)
        assert await store.get_latest_attempt_in_session("q1", "ms1") is None
        mine = await store.get_latest_attempt_in_session("q1", "ms2")
        assert mine is not None and mine.id == "a2"


@pytest.mark.asyncio
async def test_the_report_transcript_of_a_session_ignores_other_sessions_answers(db):
    async with db() as s:
        store = InterviewStore(s)
        ms1 = await store.get_mock_session("ms1")
        transcript = await session_transcript(store, ms1)
    assert [(t["question_id"], t["stem"], t["answer"]) for t in transcript] == [
        ("q1", "讲一个你拆分数据的经历", "")]


@pytest.mark.asyncio
async def test_a_question_answered_elsewhere_is_still_open_here(db):
    async with db() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")
        out = await plan(scope, mock_session_id="ms1")
    assert out["current_question_id"] == "q1"


@pytest.mark.asyncio
async def test_a_history_turn_describes_this_session_only(db):
    # The question was answered once, in another session. In this session's history it has no
    # answer, and it must not carry a counter that says it has been answered.
    from jc.services.question_bank_service import mock_session_history

    async with db() as s:
        scope = RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")
        out = await mock_session_history(scope, mock_session_id="ms1")
    assert len(out["turns"]) == 1
    turn = out["turns"][0]
    assert turn["question_id"] == "q1" and turn["user_answer"] is None
    assert "attempt_count" not in turn
