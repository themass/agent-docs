"""A simulated interviewer drives a full counted mock interview through the tool dispatcher, the
route the agent uses. The model is a script, not a real call: the point is that the catalog, the
handlers and the guards agree, and that the report comes from the reviewer path."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.mcp.handlers import dispatch_tool
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import interview_reviewer
from reviewer_agent_fake import FakeClientFactory, FakeReviewerAgent

ANSWER = "我负责把结算接口从单表拆成两张表，耗时三周。"
MUST_HAVE = ["Python", "分布式事务"]
Q_PYTHON, Q_TX = "q01", "q02"


def _stem(index: int) -> str:
    return {
        1: "讲一个你用 Python 写过的数据脚本",
        2: "你如何处理分布式事务的一致性",
    }.get(index, f"第 {index} 个通用问题：讲讲你做过的一件事")


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/flow.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user",
                            payload={"experience": "结算接口拆表"}, version=1))
        session.add(Job(id="j1", profile_id="p1", company="A", title="后端", raw_text="岗位",
                        requirements={"must_have_skills": MUST_HAVE}))
        for index in range(1, 22):
            session.add(InterviewQuestion(id=f"q{index:02d}", profile_id="p1",
                                          stem=_stem(index), question_type="behavioral"))
        session.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id="j1",
            question_ids=[], bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="pressure", quota_counted=True,
        ))
        session.add(AnswerAttempt(id="a1", question_id=Q_PYTHON, profile_id="p1",
                                  mock_session_id="ms1", user_answer=ANSWER,
                                  coach_feedback={}, reference_answer=None))
        await session.commit()
    yield maker
    await engine.dispose()


def _scope(s) -> RunScope:
    return RunScope(db=s, user_id="u1", profile_id="p1", mock_session_id="ms1")


async def _call(db, name: str, arguments: dict):
    async with db() as s:
        return await dispatch_tool(_scope(s), name, arguments)


async def _ask(db, qid: str) -> dict:
    return await _call(db, "jc_mock_ask", {"mock_session_id": "ms1", "question_id": qid,
                                           "kind": "main"})


@pytest.mark.asyncio
async def test_full_run_end_to_end_through_the_tools(db, monkeypatch):
    # Plan first: the interviewer sees the must-haves and a suggestion, not an order.
    plan = await _call(db, "jc_mock_plan", {"mock_session_id": "ms1"})
    assert plan["suggested_next"] == "Python" and plan["main_limit"] == 20

    assert (await _ask(db, Q_PYTHON))["accepted"]

    # An early end is refused while the second must-have is unasked.
    early = await _call(db, "jc_mock_end", {"mock_session_id": "ms1"})
    assert early["accepted"] is False and early["uncovered"] == ["分布式事务"]

    assert (await _ask(db, Q_TX))["accepted"]
    for index in range(3, 21):
        assert (await _ask(db, f"q{index:02d}"))["accepted"], index

    # The twenty-first main question is refused and nothing is written for it.
    over = await _ask(db, "q21")
    assert over["accepted"] is False and over["code"] == "main_limit"

    ended = await _call(db, "jc_mock_end", {"mock_session_id": "ms1"})
    assert ended["accepted"] is True and ended["asked_main"] == 20

    # The reviewer scores the session. Its quote is the candidate's own words, so it is kept.
    agent = FakeReviewerAgent(db, report={"questions": [{
        "question_id": Q_PYTHON, "scores": {"depth": 6}, "evidence": {"depth": "拆成两张表"},
    }]})
    monkeypatch.setattr(interview_reviewer, "get_deerflow_client", FakeClientFactory(agent))
    review = await _call(db, "jc_mock_review", {"mock_session_id": "ms1"})

    assert review == {"accepted": True, "mock_session_id": "ms1"}
    assert [run["skill"] for run in agent.runs] == ["interview-reviewer"]
    async with db() as s:
        stored = (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()
    assert stored.status == "completed"
    assert stored.report["questions"][0]["scores"]["depth"] == 6
    assert stored.coverage["ended_reason"] == "completed"
    assert stored.coverage["ended_early"] is False


@pytest.mark.asyncio
async def test_review_is_refused_for_a_session_that_has_not_ended(db, monkeypatch):
    agent = FakeReviewerAgent(db, report={"questions": []})
    monkeypatch.setattr(interview_reviewer, "get_deerflow_client", FakeClientFactory(agent))
    with pytest.raises(ValueError, match="after the session has ended"):
        await _call(db, "jc_mock_review", {"mock_session_id": "ms1"})
    assert agent.runs == [], "an unfinished session must not start the reviewer"
