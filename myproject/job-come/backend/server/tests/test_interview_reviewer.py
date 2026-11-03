"""The independent reviewer is an agent run of its own: its role, its model, its identity, and the
stored report read back after the run. The run itself is a fake here (see reviewer_agent_fake)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.adapters.deerflow_harness_client import model_for_skill
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import interview_reviewer
from jc.services.interview_reviewer import REVIEWER_SKILL, review_session
from reviewer_agent_fake import FakeClientFactory, FakeReviewerAgent

ANSWER = "我负责把结算接口从单表拆成两张表，耗时三周。"
GOOD_REPORT = {"questions": [{"question_id": "q1", "scores": {"depth": 6},
                              "evidence": {"depth": "拆成两张表"}}]}
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/review.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user",
                            payload={"experience": "结算接口拆表"}, version=1))
        session.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="full", question_ids=["q1"],
            bank_draw_count=0, generated_count=0, status="completed",
            started_at=datetime(2026, 11, 1, tzinfo=UTC),
        ))
        session.add(InterviewQuestion(id="q1", profile_id="p1",
                                      stem="讲一个你拆分数据的经历", question_type="behavioral"))
        session.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1",
                                  mock_session_id="ms1", user_answer=ANSWER,
                                  coach_feedback={}, reference_answer=None))
        await session.commit()
    yield factory
    await engine.dispose()


def _use(monkeypatch, agent: FakeReviewerAgent) -> None:
    monkeypatch.setattr(interview_reviewer, "get_deerflow_client", FakeClientFactory(agent))


async def _review(maker) -> bool:
    async with maker() as s:
        return await review_session(s, user_id="u1", profile_id="p1", mock_session_id="ms1",
                                    budget_seconds=5)


@pytest.mark.asyncio
async def test_the_reviewer_runs_as_its_own_agent_with_the_session_identity(maker, monkeypatch):
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT)
    _use(monkeypatch, agent)
    assert await _review(maker) is True

    run = agent.runs[0]
    assert run["skill"] == REVIEWER_SKILL == "interview-reviewer"
    assert run["metadata"].skill_hint == "interview-reviewer"
    assert run["metadata"].extra == {"mock_session_id": "ms1"}
    assert "ms1" in run["context"]["message"]
    assert "不要提问" in run["context"]["message"]
    async with maker() as s:
        stored = (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()
    assert stored.report["questions"][0]["scores"]["depth"] == 6


@pytest.mark.asyncio
async def test_a_run_that_writes_no_report_is_not_stored(maker, monkeypatch):
    _use(monkeypatch, FakeReviewerAgent(maker, report=None))
    assert await _review(maker) is False


@pytest.mark.asyncio
async def test_a_malformed_report_is_refused_by_the_tool_and_nothing_is_stored(maker, monkeypatch):
    bad = {"questions": [{"question_id": "q1", "scores": {"depth": 11}}]}
    _use(monkeypatch, FakeReviewerAgent(maker, report=bad))
    assert await _review(maker) is False


@pytest.mark.asyncio
async def test_a_run_past_its_budget_stores_nothing(maker, monkeypatch):
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT, delay=0.5)
    _use(monkeypatch, agent)
    async with maker() as s:
        result = await review_session(s, user_id="u1", profile_id="p1", mock_session_id="ms1",
                                      budget_seconds=0.05)
    assert result is False
    async with maker() as s:
        stored = (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()
    assert stored.report is None


@pytest.mark.asyncio
async def test_an_unfinished_session_never_starts_a_run(maker, monkeypatch):
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT)
    _use(monkeypatch, agent)
    async with maker() as s:
        session = await s.get(MockSession, "ms1")
        session.status = "active"
        await s.commit()
    with pytest.raises(ValueError, match="after the session has ended"):
        await _review(maker)
    assert agent.runs == []


def test_the_reviewer_skill_runs_on_the_reviewer_model():
    assert model_for_skill("interview-reviewer") == "jc-reviewer"
    assert model_for_skill("coach-mock") is None


def test_the_reviewer_model_is_configured_on_the_reviewer_scenario():
    config = yaml.safe_load((BACKEND / "agent" / "deerflow" / "config.yaml").read_text("utf-8"))
    routing = yaml.safe_load((BACKEND / "agent" / "llm" / "routing.yaml").read_text("utf-8"))
    entry = next(m for m in config["models"] if m["name"] == "jc-reviewer")
    assert entry["model"] == "reviewer"
    assert "reviewer" in routing["scenarios"]
