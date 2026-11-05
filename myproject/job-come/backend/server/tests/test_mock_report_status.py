"""The report page only reads. Opening it never starts a review; it shows where the report stands
(pending, failed with a retry, ready), and the retry puts a failed report back in the queue."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from agentkit.web.auth import UserActor
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.agent import subtask
from jc.api import coach_router
from jc.api.auth_router import register_exception_handlers
from jc.api.deps import get_coach_service, require_user
from jc.db.base import Base
from jc.exceptions import ConflictError, ForbiddenError, NotFoundError
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import mock_report_queue
from jc.services.interview_service import InterviewService
from jc.services.mock_report_queue import MAX_REPORT_RUNS, claim_next_report, generate_report
from reviewer_agent_fake import FakeClientFactory, FakeReviewerAgent

ANSWER = "我负责把结算接口从单表拆成两张表，耗时三周。"
GOOD_REPORT = {"questions": [{"question_id": "q1", "scores": {"depth": 6},
                              "evidence": {"depth": "拆成两张表"}}]}
OWNER = UserActor(user_id="u1", session_id="s")
OTHER = UserActor(user_id="u2", session_id="s")


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/status.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        db.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        db.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲一个你拆分数据的经历",
                                 question_type="behavioral"))
        db.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
                             user_answer=ANSWER, coach_feedback={}, reference_answer=None))
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", question_ids=["q1"],
            bank_draw_count=0, generated_count=0, status="completed", style="gentle",
            quota_counted=True, started_at=datetime(2026, 11, 5, tzinfo=UTC),
            completed_at=datetime(2026, 11, 5, 1, tzinfo=UTC),
            coverage={"asked": [{"question_id": "q1", "kind": "main"}]},
        ))
        await db.commit()
    yield makers
    await engine.dispose()


async def _set(maker, **values) -> None:
    async with maker() as db:
        session = await db.get(MockSession, "ms1")
        for name, value in values.items():
            setattr(session, name, value)
        await db.commit()


async def _report(maker, actor=OWNER):
    async with maker() as db:
        return await InterviewService(db).get_mock_report("ms1", actor=actor)


@pytest.mark.asyncio
async def test_opening_the_report_of_a_queued_session_does_not_call_the_reviewer(
    maker, monkeypatch
):
    await _set(maker, report_status="queued")
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT)
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))
    out = await _report(maker)
    assert out.status == "pending" and out.questions == [] and out.can_retry is False
    assert "正在生成" in out.message
    assert agent.runs == []


@pytest.mark.asyncio
async def test_a_report_being_generated_reads_as_pending(maker):
    await _set(maker, report_status="generating", report_attempts=1)
    out = await _report(maker)
    assert out.status == "pending" and out.can_retry is False


@pytest.mark.asyncio
async def test_a_failed_report_says_why_and_offers_a_retry_until_the_runs_are_used(maker):
    await _set(maker, report_status="failed", report_attempts=2, report_error="评审没有产出报告。")
    out = await _report(maker)
    assert (out.status, out.message, out.can_retry) == ("failed", "评审没有产出报告。", True)
    await _set(maker, report_attempts=MAX_REPORT_RUNS)
    out = await _report(maker)
    assert out.status == "failed" and out.can_retry is False


@pytest.mark.asyncio
async def test_a_stored_report_is_shown_even_if_the_status_has_not_caught_up(maker):
    # The reviewer's tool stores the report before the worker flips the status to ready.
    await _set(maker, report_status="generating", report_attempts=1,
               report={"overall": {"depth": 6.0}, "questions": [
                   {"question_id": "q1", "scores": {"depth": 6}, "evidence": {}}], "checks": {}})
    out = await _report(maker)
    assert out.status == "ready" and out.overall["depth"] == 6.0


@pytest.mark.asyncio
async def test_a_report_generated_through_the_queue_is_read_not_produced_again(maker, monkeypatch):
    await _set(maker, report_status="queued")
    agent = FakeReviewerAgent(maker, report=GOOD_REPORT)
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))
    monkeypatch.setattr(mock_report_queue, "AsyncSessionLocal", maker)
    async with maker() as db:
        assert await claim_next_report(db) == "ms1"
    assert await generate_report("ms1") is True
    first = await _report(maker)
    second = await _report(maker)
    assert first.status == second.status == "ready"
    assert first.questions[0].answer == ANSWER and first.style == "gentle"
    assert len(agent.runs) == 1


@pytest.mark.asyncio
async def test_a_completed_session_nobody_will_pick_up_is_failed_not_pending_forever(maker):
    # Nothing would ever pick it up, so "pending" would never end.
    await _set(maker, report_status=None)
    out = await _report(maker)
    assert out.status == "failed" and out.can_retry is False


@pytest.mark.asyncio
async def test_retry_requeues_a_failed_report(maker):
    await _set(maker, report_status="failed", report_attempts=1, report_error="评审没有产出报告。")
    async with maker() as db:
        out = await InterviewService(db).retry_mock_report("ms1", actor=OWNER)
    assert out.status == "pending" and out.can_retry is False
    async with maker() as db:
        row = (await db.execute(select(MockSession))).scalar_one()
    assert (row.report_status, row.report_error) == ("queued", None)


@pytest.mark.asyncio
async def test_retry_is_refused_once_every_run_has_been_used(maker):
    await _set(maker, report_status="failed", report_attempts=MAX_REPORT_RUNS)
    async with maker() as db:
        with pytest.raises(ConflictError) as exc:
            await InterviewService(db).retry_mock_report("ms1", actor=OWNER)
    assert exc.value.code == "mock_report_retry_exhausted"
    assert (await _report(maker)).status == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("attempts", [0, MAX_REPORT_RUNS])
@pytest.mark.parametrize("status", ["queued", "generating", "ready"])
async def test_retry_is_refused_for_a_report_that_has_not_failed(maker, status, attempts):
    # With every run used, a report that is not failed is still "not failed", not "exhausted".
    await _set(maker, report_status=status, report_attempts=attempts)
    async with maker() as db:
        with pytest.raises(ConflictError) as exc:
            await InterviewService(db).retry_mock_report("ms1", actor=OWNER)
    assert exc.value.code == "mock_report_not_failed"


@pytest.mark.asyncio
async def test_retry_of_another_users_session_is_refused_and_changes_nothing(maker):
    await _set(maker, report_status="failed", report_attempts=1)
    async with maker() as db:
        with pytest.raises((ForbiddenError, NotFoundError)):
            await InterviewService(db).retry_mock_report("ms1", actor=OTHER)
    async with maker() as db:
        assert (await db.execute(select(MockSession))).scalar_one().report_status == "failed"


@pytest.mark.asyncio
async def test_the_retry_route_answers_409_when_the_runs_are_used_and_the_page_shows_it(maker):
    await _set(maker, report_status="failed", report_attempts=MAX_REPORT_RUNS)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(coach_router.router)

    async def _service():
        async with maker() as db:
            yield InterviewService(db)

    app.dependency_overrides[require_user] = lambda: OWNER
    app.dependency_overrides[get_coach_service] = _service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        page = await client.get("/coach/mock/sessions/ms1/report")
        retry = await client.post("/coach/mock/sessions/ms1/report/retry")
    assert page.status_code == 200
    assert page.json()["status"] == "failed" and page.json()["can_retry"] is False
    assert retry.status_code == 409 and retry.json()["code"] == "mock_report_retry_exhausted"


@pytest.mark.asyncio
async def test_the_retry_route_requeues_a_failed_report(maker):
    await _set(maker, report_status="failed", report_attempts=1)
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(coach_router.router)

    async def _service():
        async with maker() as db:
            yield InterviewService(db)

    app.dependency_overrides[require_user] = lambda: OWNER
    app.dependency_overrides[get_coach_service] = _service
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://fixture"
    ) as client:
        retry = await client.post("/coach/mock/sessions/ms1/report/retry")
    assert retry.status_code == 200 and retry.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_the_app_runs_the_report_dispatcher_for_its_lifetime(monkeypatch):
    from jc import main as app_main
    from jc import tasks

    events: list[str] = []

    async def fake_report_dispatcher(**_):
        events.append("report:start")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            events.append("report:cancelled")
            raise

    async def fake_parse_dispatcher(**_):
        await asyncio.sleep(3600)

    monkeypatch.setattr(mock_report_queue, "run_mock_report_dispatcher", fake_report_dispatcher)
    monkeypatch.setattr(tasks, "run_profile_parse_dispatcher", fake_parse_dispatcher)
    monkeypatch.setattr("jc.llm.bootstrap.configure_litellm", lambda: None)
    monkeypatch.setattr("jc.observability.langfuse_setup.setup_langfuse_callbacks", lambda: None)

    # Bounded, and the bound must not be what ends it: the app swallows a CancelledError while
    # shutting down, so a dispatcher it forgot to cancel would be cancelled by this timeout and
    # the test would pass.
    bound = asyncio.timeout(5)
    async with bound:
        async with app_main.lifespan(SimpleNamespace()):
            await asyncio.sleep(0.05)
            assert events == ["report:start"]
    assert not bound.expired(), "shutdown waited on a dispatcher it never cancelled"
    assert events == ["report:start", "report:cancelled"]
