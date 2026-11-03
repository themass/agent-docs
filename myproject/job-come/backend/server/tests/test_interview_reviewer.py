"""The independent reviewer runs on the `reviewer` scenario, sees the session and profile but never
the interviewer's plan, and stores a report only when it finishes within its budget."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import interview_reviewer
from jc.services.interview_reviewer import run_review

ANSWER = "我负责把结算接口从单表拆成两张表，耗时三周。"


class FakeRouter:
    def __init__(self, response: Any, delay: float = 0.0) -> None:
        self.response = response
        self.delay = delay
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def acompletion(self, scenario: str, **kwargs: Any) -> Any:
        self.calls.append((scenario, kwargs))
        await asyncio.sleep(self.delay)
        return kwargs["response_validator"](self.response)

    def content_from_response(self, response: Any) -> str:
        return json.dumps(response, ensure_ascii=False)


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/review.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
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
    yield maker
    await engine.dispose()


RESPONSE = {"questions": [{"question_id": "q1", "scores": {"depth": 6},
                           "evidence": {"depth": "拆成两张表"}}]}


def _scope(db_session) -> RunScope:
    return RunScope(db=db_session, user_id="u1", profile_id="p1", mock_session_id="ms1")


@pytest.mark.asyncio
async def test_reviewer_uses_its_own_scenario_and_sees_no_plan(db, monkeypatch):
    router = FakeRouter(RESPONSE)
    monkeypatch.setattr(interview_reviewer, "get_llm_router", lambda: router)
    async with db() as s:
        out = await run_review(_scope(s), mock_session_id="ms1")

    assert out["overall"]["depth"] == 6.0
    scenario, kwargs = router.calls[0]
    assert scenario == "reviewer"
    assert kwargs["response_format"] == {"type": "json_object"}
    sent = json.dumps(kwargs["messages"], ensure_ascii=False)
    assert "讲一个你拆分数据的经历" in sent and ANSWER in sent
    assert "结算接口拆表" in sent
    assert "plan" not in sent.lower()


@pytest.mark.asyncio
async def test_completed_review_is_stored_on_the_session(db, monkeypatch):
    monkeypatch.setattr(interview_reviewer, "get_llm_router", lambda: FakeRouter(RESPONSE))
    async with db() as s:
        await run_review(_scope(s), mock_session_id="ms1")
    async with db() as s:
        stored = (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()
        assert stored.report["questions"][0]["scores"]["depth"] == 6


@pytest.mark.asyncio
async def test_unfinished_session_never_reaches_the_model(db, monkeypatch):
    router = FakeRouter(RESPONSE)
    monkeypatch.setattr(interview_reviewer, "get_llm_router", lambda: router)
    async with db() as s:
        session = await s.get(MockSession, "ms1")
        session.status = "active"
        await s.commit()
    async with db() as s:
        with pytest.raises(ValueError, match="after the session has ended"):
            await run_review(_scope(s), mock_session_id="ms1")
    assert router.calls == []


@pytest.mark.asyncio
async def test_review_past_its_budget_stores_nothing(db, monkeypatch):
    monkeypatch.setattr(interview_reviewer, "get_llm_router",
                        lambda: FakeRouter(RESPONSE, delay=0.5))
    async with db() as s:
        with pytest.raises(TimeoutError):
            await run_review(_scope(s), mock_session_id="ms1", budget_seconds=0.05)
    async with db() as s:
        stored = (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()
        assert stored.report is None
