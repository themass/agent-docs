"""The report page reads a finished session's stored review; the candidate's finish button ends the
session through the same guard as the interviewer; a finished session is reviewed once."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.agent import subtask
from jc.db.base import Base
from jc.exceptions import ForbiddenError, NotFoundError
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.interview_service import InterviewService
from reviewer_agent_fake import FakeClientFactory, FakeReviewerAgent

ANSWER = "我负责把结算接口从单表拆成两张表，耗时三周。"
OWNER = UserActor(user_id="u1", session_id="s")
OTHER = UserActor(user_id="u2", session_id="s")


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/view.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        session.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user",
                            payload={"experience": "结算接口拆表"}, version=1))
        session.add(InterviewQuestion(id="q1", profile_id="p1",
                                      stem="讲一个你拆分数据的经历", question_type="behavioral"))
        session.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1",
                                  mock_session_id="ms1", user_answer=ANSWER,
                                  coach_feedback={}, reference_answer=None))
        session.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", question_ids=["q1"],
            bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="gentle", quota_counted=True,
        ))
        await session.commit()
    yield factory
    await engine.dispose()


async def _set_status(maker, status: str) -> None:
    async with maker() as s:
        session = await s.get(MockSession, "ms1")
        session.status = status
        await s.commit()


@pytest.mark.asyncio
async def test_active_session_has_no_report_yet(maker):
    async with maker() as s:
        out = await InterviewService(s).get_mock_report("ms1", actor=OWNER)
    assert out.status == "active" and out.questions == []


@pytest.mark.asyncio
async def test_another_user_cannot_read_the_report(maker):
    await _set_status(maker, "completed")
    async with maker() as s:
        # The profile check refuses first, as get_mock_session does; either refusal denies the read.
        with pytest.raises((ForbiddenError, NotFoundError)):
            await InterviewService(s).get_mock_report("ms1", actor=OTHER)


@pytest.mark.asyncio
async def test_finished_session_is_reviewed_once_and_read_after(maker, monkeypatch):
    await _set_status(maker, "completed")
    agent = FakeReviewerAgent(maker, report={"questions": [{
        "question_id": "q1", "scores": {"depth": 6}, "evidence": {"depth": "拆成两张表"},
        "praise": "讲清了动作。", "fixes": [{"severity": "suggest", "text": "补上结果。"}],
        "reference": [],
    }]})
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))

    async with maker() as s:
        first = await InterviewService(s).get_mock_report("ms1", actor=OWNER)
    async with maker() as s:
        second = await InterviewService(s).get_mock_report("ms1", actor=OWNER)

    assert first.status == "ready" and first.style == "gentle"
    assert first.questions[0].stem == "讲一个你拆分数据的经历"
    assert first.questions[0].answer == ANSWER
    assert first.overall["depth"] == 6.0
    assert second.questions[0].praise == "讲清了动作。"
    assert len(agent.runs) == 1, "the stored report is read, not produced again"


@pytest.mark.asyncio
async def test_failed_review_is_pending_not_an_error(maker, monkeypatch):
    await _set_status(maker, "completed")
    agent = FakeReviewerAgent(maker, error=RuntimeError("agent unavailable"))
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))
    async with maker() as s:
        out = await InterviewService(s).get_mock_report("ms1", actor=OWNER)
    assert out.status == "pending" and out.questions == []


@pytest.mark.asyncio
async def test_finish_button_ends_the_session_as_an_early_end(maker):
    async with maker() as s:
        out = await InterviewService(s).complete_mock_session("ms1", actor=OWNER)
    assert out.status == "completed"
    async with maker() as s:
        session = await s.get(MockSession, "ms1")
    assert session.coverage["ended_reason"] == "user_ended"
    assert session.coverage["ended_early"] is True


@pytest.mark.asyncio
async def test_a_warmup_gets_the_brief_report_without_question_detail(maker, monkeypatch):
    async with maker() as s:
        session = await s.get(MockSession, "ms1")
        session.status = "completed"
        session.quota_counted = False
        await s.commit()
    agent = FakeReviewerAgent(maker, report={"questions": [{
        "question_id": "q1", "scores": {"depth": 6}, "evidence": {"depth": "拆成两张表"},
    }]})
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))
    async with maker() as s:
        out = await InterviewService(s).get_mock_report("ms1", actor=OWNER)
    assert out.status == "ready" and out.brief is True
    assert out.questions == []
    assert out.overall["depth"] == 6.0
    assert out.suggestions[0].dimension == "depth"
    assert out.suggestions[0].question_id == "q1"
    assert out.trend is None
