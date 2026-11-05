"""A page that reloads finds the interview that is still running.

The page used to keep the mock session id only in memory, so a reload forgot the interview: answers
stopped being recorded, the interviewer was told no session was open, and starting again opened a
second one (a full run then hit the monthly quota because the first still held it)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from agentkit.web.auth import UserActor
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.api import coach_router
from jc.api.auth_router import register_exception_handlers
from jc.api.deps import get_coach_service, require_user
from jc.db.base import Base
from jc.exceptions import ForbiddenError, NotFoundError
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.interview_service import InterviewService

OWNER = UserActor(user_id="u1", session_id="s")
OTHER = UserActor(user_id="u2", session_id="s")


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/active.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        db.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        await db.commit()
    yield makers
    await engine.dispose()


async def _seed(
    maker, session_id, *, job_id="j1", status="active", started=None, last_activity=None
):
    coverage = {"asked": []}
    if last_activity:
        coverage["last_activity"] = last_activity
    async with maker() as db:
        db.add(MockSession(
            id=session_id, profile_id="p1", user_id="u1", mode="target", job_id=job_id,
            question_ids=[], bank_draw_count=0, generated_count=0, status=status,
            started_at=started or datetime.now(UTC), style="standard", level="mid",
            quota_counted=False, coverage=coverage,
        ))
        await db.commit()


async def _active(maker, *, job_id="j1", actor=OWNER):
    async with maker() as db:
        return await InterviewService(db).active_mock_session("p1", job_id=job_id, actor=actor)


@pytest.mark.asyncio
async def test_the_running_interview_for_this_job_is_found(maker):
    await _seed(maker, "ms_run")
    found = await _active(maker)
    assert found is not None and found.id == "ms_run" and found.status == "active"
    assert found.level == "mid" and found.job_id == "j1"


@pytest.mark.asyncio
async def test_no_interview_is_found_when_none_is_running(maker):
    await _seed(maker, "ms_done", status="completed")
    assert await _active(maker) is None


@pytest.mark.asyncio
async def test_an_interview_for_another_job_is_not_this_jobs_interview(maker):
    await _seed(maker, "ms_other", job_id="j2")
    assert await _active(maker, job_id="j1") is None
    assert (await _active(maker, job_id="j2")).id == "ms_other"


@pytest.mark.asyncio
async def test_the_newest_running_interview_wins(maker):
    now = datetime.now(UTC)
    await _seed(maker, "ms_old", started=now - timedelta(hours=3))
    await _seed(maker, "ms_new", started=now - timedelta(hours=1))
    assert (await _active(maker)).id == "ms_new"


@pytest.mark.asyncio
async def test_an_interview_left_idle_past_the_limit_is_closed_not_resumed(maker):
    stale = (datetime.now(UTC) - timedelta(days=3)).replace(tzinfo=None).isoformat()
    await _seed(maker, "ms_stale", started=datetime.now(UTC) - timedelta(days=3),
                last_activity=stale)
    assert await _active(maker) is None
    async with maker() as db:
        row = (await db.execute(select(MockSession))).scalar_one()
    assert row.status == "completed" and row.report_status == "failed"


@pytest.mark.asyncio
async def test_another_users_profile_is_refused(maker):
    await _seed(maker, "ms_run")
    with pytest.raises((ForbiddenError, NotFoundError)):
        await _active(maker, actor=OTHER)


@pytest.mark.asyncio
async def test_a_running_interview_started_by_someone_else_is_not_handed_over(maker):
    # A profile can change hands (a guest profile merged into an account). An interview the
    # previous owner left running on it is not the new owner's to resume.
    async with maker() as db:
        db.add(MockSession(
            id="ms_theirs", profile_id="p1", user_id="u2", mode="target", job_id="j1",
            question_ids=[], bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="standard", coverage={"asked": []},
        ))
        await db.commit()
    assert await _active(maker) is None


@pytest.mark.asyncio
async def test_the_route_returns_the_interview_or_null(maker):
    await _seed(maker, "ms_run")
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
        url = "/coach/profiles/p1/mock-sessions/active"
        found = await client.get(url, params={"job_id": "j1"})
        nothing = await client.get(url, params={"job_id": "j9"})
        missing = await client.get(url)
    assert found.status_code == 200 and found.json()["id"] == "ms_run"
    assert nothing.status_code == 200 and nothing.json() is None
    assert missing.status_code == 422
