"""Guards for the interviewer: refusals return a reason and write nothing; limits follow the
session."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.models.interview import InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import mock_guard_service as guard

STEMS = {
    "q1": "讲一个你用 Python 写过的数据脚本",
    "q2": "你如何处理分布式事务的一致性",
    "q3": "讲讲你做过的缓存设计",
    "q4": "讲一个团队协作的经历",
    "q5": "你怎么做代码评审",
    "q6": "你怎么排查线上问题",
    "q7": "你怎么学习新技术",
}


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/guard.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        session.add(User(id="u2", email="u2@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user", payload={}, version=1))
        session.add(Profile(id="p2", user_id="u2", owner_kind="user", payload={}, version=1))
        session.add(Job(
            id="j1", profile_id="p1", company="A", title="后端", raw_text="岗位描述",
            requirements={"must_have_skills": ["Python", "分布式事务"]},
        ))
        for qid, stem in STEMS.items():
            session.add(InterviewQuestion(id=qid, profile_id="p1", stem=stem,
                                          question_type="behavioral"))
        session.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id="j1",
            question_ids=[], bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime(2026, 11, 1, tzinfo=UTC), style="standard",
        ))
        await session.commit()
    yield maker
    await engine.dispose()


def _scope(s, profile_id: str = "p1") -> RunScope:
    return RunScope(db=s, user_id="u1", profile_id=profile_id, mock_session_id="ms1")


async def _session(db) -> MockSession:
    async with db() as s:
        return (await s.execute(select(MockSession).where(MockSession.id == "ms1"))).scalar_one()


async def _ask(db, qid: str, kind: str = "main", parent: str | None = None) -> dict:
    async with db() as s:
        return await guard.ask(_scope(s), mock_session_id="ms1", question_id=qid,
                               kind=kind, parent_question_id=parent)


@pytest.mark.asyncio
async def test_plan_suggests_the_first_uncovered_must_have_in_jd_order(db):
    async with db() as s:
        out = await guard.plan(_scope(s), mock_session_id="ms1")
    assert out["must_have"] == ["Python", "分布式事务"]
    assert out["uncovered"] == ["Python", "分布式事务"]
    assert out["suggested_next"] == "Python"
    assert out["main_limit"] == 5 and out["remaining_main"] == 5


@pytest.mark.asyncio
async def test_asked_question_is_recorded_and_moves_the_plan(db):
    out = await _ask(db, "q1")
    assert out == {"accepted": True, "asked_main": 1, "remaining_main": 4}
    session = await _session(db)
    assert session.question_ids == ["q1"]
    async with db() as s:
        plan = await guard.plan(_scope(s), mock_session_id="ms1")
    assert plan["covered"] == ["Python"]
    assert plan["suggested_next"] == "分布式事务"


@pytest.mark.asyncio
async def test_main_question_over_the_warmup_limit_is_refused_and_not_written(db):
    for qid in ["q1", "q3", "q4", "q5", "q6"]:
        assert (await _ask(db, qid))["accepted"]
    refused = await _ask(db, "q7")
    assert refused["accepted"] is False and refused["code"] == "main_limit"
    assert "q7" not in (await _session(db)).question_ids


@pytest.mark.asyncio
async def test_counted_full_run_allows_twenty_main_questions(db):
    async with db() as s:
        session = await s.get(MockSession, "ms1")
        session.quota_counted = True
        await s.commit()
    for qid in ["q1", "q2", "q3", "q4", "q5", "q6"]:
        assert (await _ask(db, qid))["accepted"], qid


@pytest.mark.asyncio
async def test_followup_needs_an_asked_main_question_and_is_capped(db):
    refused = await _ask(db, "q2", kind="followup", parent="q1")
    assert refused["accepted"] is False and refused["code"] == "parent_not_asked"

    assert (await _ask(db, "q1"))["accepted"]
    assert (await _ask(db, "q3", kind="followup", parent="q1"))["accepted"]
    capped = await _ask(db, "q4", kind="followup", parent="q1")
    assert capped["accepted"] is False and capped["code"] == "followup_limit"


@pytest.mark.asyncio
async def test_question_already_asked_is_refused(db):
    assert (await _ask(db, "q1"))["accepted"]
    again = await _ask(db, "q1")
    assert again["accepted"] is False and again["code"] == "already_asked"


@pytest.mark.asyncio
async def test_end_is_refused_while_a_must_have_is_unasked_and_under_the_limit(db):
    assert (await _ask(db, "q1"))["accepted"]
    async with db() as s:
        out = await guard.end(_scope(s), mock_session_id="ms1")
    assert out["accepted"] is False and out["code"] == "uncovered"
    assert out["uncovered"] == ["分布式事务"]
    assert (await _session(db)).status == "active"


@pytest.mark.asyncio
async def test_end_is_allowed_once_every_must_have_is_covered(db):
    assert (await _ask(db, "q1"))["accepted"]
    assert (await _ask(db, "q2"))["accepted"]
    async with db() as s:
        out = await guard.end(_scope(s), mock_session_id="ms1")
    assert out["accepted"] is True and out["ended_early"] is False
    session = await _session(db)
    assert session.status == "completed" and session.completed_at is not None


@pytest.mark.asyncio
async def test_user_ended_is_allowed_and_recorded_as_early(db):
    async with db() as s:
        out = await guard.end(_scope(s), mock_session_id="ms1", reason="user_ended")
    assert out["accepted"] is True and out["ended_early"] is True
    assert (await _session(db)).coverage["ended_reason"] == "user_ended"


@pytest.mark.asyncio
async def test_no_question_or_end_is_accepted_after_the_session_closed(db):
    async with db() as s:
        await guard.end(_scope(s), mock_session_id="ms1", reason="user_ended")
    assert (await _ask(db, "q1"))["code"] == "session_closed"
    async with db() as s:
        again = await guard.end(_scope(s), mock_session_id="ms1")
    assert again["code"] == "session_closed"


@pytest.mark.asyncio
async def test_another_profiles_session_is_refused(db):
    async with db() as s:
        with pytest.raises(PermissionError):
            await guard.plan(_scope(s, profile_id="p2"), mock_session_id="ms1")
