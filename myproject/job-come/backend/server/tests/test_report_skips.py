"""A report cannot rate an interview highly on the strength of questions that were never answered.

Skipping is free (only swapping is limited), so a candidate can skip nearly everything. The guard
already says a skipped question covers nothing; the report must say the same, and the tier must not
rise on a handful of answers. Found in review: four of five questions skipped, one answered at 9,
four must-haves each matched by a different question, rated "表现稳定"."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.interview_service import InterviewService

OWNER = UserActor(user_id="u1", session_id="s")
DIMS = ("structure", "relevance", "depth", "communication", "reflection")
MUST = ["Python", "Kafka", "Redis", "MySQL"]
STEMS = {
    "q1": "讲一个你用 Python 写过的数据脚本",
    "q2": "你们怎么用 Kafka 做异步处理",
    "q3": "Redis 缓存是怎么设计的",
    "q4": "MySQL 的索引你怎么优化",
    "q5": "说说你觉得自己最大的缺点",
}
FOLLOW_STEMS = {
    "f1": "脚本跑失败了怎么重试",
    "f2": "每天凌晨跑是怎么调度的",
    "f3": "三周里最难的一步是什么",
}
ANSWER = "我用 Python 写过结算对账脚本，每天凌晨跑，耗时三周做完。"


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/skips.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算"}, version=1))
        db.add(Job(id="j1", profile_id="p1", company="示例", title="后端工程师", raw_text="岗位",
                   tag="warmup", fit_gaps=[], fit_blockers=[], status="active",
                   requirements={"must_have_skills": MUST}))
        for qid, stem in {**STEMS, **FOLLOW_STEMS}.items():
            db.add(InterviewQuestion(id=qid, profile_id="p1", stem=stem,
                                     question_type="behavioral"))
        await db.commit()
    yield makers
    await engine.dispose()


async def _page(maker, *, skipped, answered, listed, scores=9, followups=()):
    """A finished session of five main questions, then any `followups` (ids of FOLLOW_STEMS, each
    asked after q1). `skipped` and `answered` are sets of ids; the reviewer's report lists the ids
    in `listed`."""
    asked = [{"question_id": q, "kind": "main", "parent_question_id": None,
              **({"skipped": True} if q in skipped else {})} for q in STEMS]
    asked += [{"question_id": f, "kind": "followup", "parent_question_id": "q1"}
              for f in followups]
    async with maker() as db:
        for qid in answered:
            db.add(AnswerAttempt(id=f"a_{qid}", question_id=qid, profile_id="p1",
                                 mock_session_id="ms1", user_answer=ANSWER, coach_feedback={},
                                 reference_answer=None))
        report = {
            "overall": {dim: float(scores) for dim in DIMS},
            "questions": [
                {"question_id": q, "evidence": {}, "praise": None, "fixes": [], "reference": [],
                 "scores": {} if q in skipped else {"depth": scores}}
                for q in STEMS if q in listed
            ],
            "checks": {},
            "summary": None,
        }
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id="j1",
            question_ids=[*STEMS, *followups], bank_draw_count=0, generated_count=0,
            status="completed",
            started_at=datetime(2026, 11, 5, tzinfo=UTC), completed_at=datetime(2026, 11, 5, 1,
                                                                               tzinfo=UTC),
            quota_counted=True, level="mid", report=report, report_status="ready",
            coverage={"asked": asked, "ended_reason": "completed", "ended_early": False},
        ))
        await db.commit()
    async with maker() as db:
        return await InterviewService(db).get_mock_report("ms1", actor=OWNER)


@pytest.mark.asyncio
async def test_skipped_questions_do_not_count_as_covering_the_must_haves(maker):
    page = await _page(maker, skipped={"q2", "q3", "q4", "q5"}, answered={"q1"}, listed=set(STEMS))
    assert page.coverage.total == 4
    assert page.coverage.asked == 1, "only the Python question was put to the candidate"


@pytest.mark.asyncio
async def test_an_interview_that_is_mostly_skipped_is_not_rated_solid(maker):
    page = await _page(maker, skipped={"q2", "q3", "q4", "q5"}, answered={"q1"}, listed=set(STEMS))
    assert page.readiness.tier == "targeted"
    assert any("回答" in line and "1" in line and "5" in line for line in page.readiness.basis)


@pytest.mark.asyncio
async def test_answering_fewer_than_half_the_questions_caps_the_tier_by_itself(maker):
    # Nothing skipped, only one answered: the other four were asked and left unanswered.
    page = await _page(maker, skipped=set(), answered={"q1"}, listed=set(STEMS))
    assert page.readiness.tier == "targeted"
    assert any("回答" in line and "1" in line and "5" in line for line in page.readiness.basis)


@pytest.mark.asyncio
async def test_a_question_the_reviewer_left_out_still_counts_as_asked(maker):
    # The reviewer listed only q1, but q2 was put to the candidate and answered.
    page = await _page(maker, skipped={"q3", "q4", "q5"}, answered={"q1", "q2"}, listed={"q1"})
    assert page.coverage.asked == 2


@pytest.mark.asyncio
async def test_a_fully_answered_interview_that_met_the_must_haves_is_still_solid(maker):
    page = await _page(maker, skipped=set(), answered=set(STEMS), listed=set(STEMS))
    assert page.coverage.asked == 4 and page.coverage.meet == 4
    assert page.readiness.tier == "solid"
    assert all("回答" not in line for line in page.readiness.basis)


@pytest.mark.asyncio
async def test_answered_follow_ups_do_not_make_up_for_unanswered_main_questions(maker):
    # One main question answered out of five. Three answered follow-ups would make it 4 of 8 if they
    # were counted as questions, which would just clear the bar; they are not questions.
    page = await _page(maker, skipped={"q2", "q3", "q4", "q5"}, answered={"q1", "f1", "f2", "f3"},
                       listed=set(STEMS), followups=("f1", "f2", "f3"))
    assert page.readiness.tier == "targeted"
    assert any("5 道主问题里只回答了 1 道" in line for line in page.readiness.basis)
