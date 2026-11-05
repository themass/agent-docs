"""The shape of an interview is kept by the tools, not left to the interviewer's memory.

An interview opens, digs into the candidate's experience, covers the job, tests judgement in
situations, gives the candidate a turn to ask, and closes. The plan says which stage it is in and
which comes next; the candidate's own questions have a stage of their own, which has to happen
before an interview can end as completed; and a question the interviewer makes up is checked
before it is put (not a page long, not the one it just asked in other words)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.mcp.handlers import dispatch_tool
from jc.models.interview import InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.mock_answer_recorder import record_mock_answer
from jc.skills.loader import require_skill

STEMS = [
    "讲一个你拆分数据的经历",
    "讲一次线上故障的排查过程",
    "你怎么看待缓存一致性问题",
    "团队里有分歧时你怎么推进",
    "如果重新做一次你会改哪里",
]


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/stages.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        db.add(Job(id="j1", profile_id="p1", company="示例科技", title="后端工程师",
                   raw_text="岗位", tag="warmup", fit_gaps=[], fit_blockers=[], status="active",
                   requirements={"must_have_skills": ["Kafka"]}))
        db.add(InterviewQuestion(id="bank1", profile_id="p1", stem="讲讲你的缓存设计",
                                 question_type="behavioral"))
        await db.commit()
    yield makers
    await engine.dispose()


async def _open(maker, *, job_id=None, quota=False):
    async with maker() as db:
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id=job_id,
            question_ids=[], bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="standard", level="mid", quota_counted=quota,
            coverage={"asked": []},
        ))
        await db.commit()


async def _call(maker, name, arguments=None):
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        return await dispatch_tool(scope, name, {"mock_session_id": "ms1", **(arguments or {})})


async def _ask(maker, stem, **extra):
    return await _call(maker, "jc_mock_ask", {"stem": stem, **extra})


async def _plan(maker):
    return await _call(maker, "jc_mock_plan")


async def _stem_count(maker, stem):
    async with maker() as db:
        return (await db.execute(select(func.count()).select_from(InterviewQuestion)
                                 .where(InterviewQuestion.stem == stem))).scalar_one()


# --- where the interview is ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_before_the_first_question_the_interview_is_opening(maker):
    await _open(maker)
    plan = await _plan(maker)
    assert (plan["stage"], plan["suggested_stage"]) == ("opening", "experience")
    assert plan["candidate_qa"] is False and plan["stage_counts"] == {}


@pytest.mark.asyncio
async def test_the_suggested_stage_moves_on_as_the_questions_are_asked(maker):
    # A warm-up has five main questions: 2 on experience, 2 on the job, then situations, then the
    # candidate's turn.
    await _open(maker)
    seen = []
    for stem in STEMS:
        seen.append((await _plan(maker))["suggested_stage"])
        await _ask(maker, stem)
    seen.append((await _plan(maker))["suggested_stage"])
    assert seen == ["experience", "experience", "core", "core", "scenario", "candidate_qa"]


@pytest.mark.asyncio
async def test_a_question_can_say_which_stage_it_belongs_to(maker):
    await _open(maker)
    await _ask(maker, STEMS[0], stage="experience")
    await _ask(maker, STEMS[1], stage="core")
    await _ask(maker, STEMS[2], stage="core")
    plan = await _plan(maker)
    assert plan["stage"] == "core"
    assert plan["stage_counts"] == {"experience": 1, "core": 2}


@pytest.mark.asyncio
async def test_a_question_that_does_not_say_leaves_the_stage_to_the_plan(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    plan = await _plan(maker)
    assert plan["stage"] == "experience" and plan["stage_counts"] == {}


@pytest.mark.asyncio
async def test_a_stage_that_is_not_one_of_the_asking_stages_is_an_error(maker):
    await _open(maker)
    for bad in ("opening", "candidate_qa", "closing", "warmup", ""):
        with pytest.raises(ValueError, match="stage"):
            await _ask(maker, STEMS[0], stage=bad or " ")
    assert (await _plan(maker))["asked_main"] == 0


# --- the candidate's turn to ask -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_candidates_turn_cannot_open_before_any_question_was_asked(maker):
    await _open(maker)
    out = await _call(maker, "jc_mock_open_qa")
    assert out["accepted"] is False and out["code"] == "not_started"
    assert (await _plan(maker))["candidate_qa"] is False


@pytest.mark.asyncio
async def test_the_candidates_turn_waits_until_the_jobs_must_haves_were_asked_about(maker):
    await _open(maker, job_id="j1")
    await _ask(maker, STEMS[0])
    out = await _call(maker, "jc_mock_open_qa")
    assert out["accepted"] is False and out["code"] == "uncovered"
    assert out["uncovered"] == ["Kafka"]
    await _ask(maker, "你们用 Kafka 做过什么")
    assert (await _call(maker, "jc_mock_open_qa"))["accepted"] is True


@pytest.mark.asyncio
async def test_opening_the_candidates_turn_changes_the_stage_and_clears_the_table(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    out = await _call(maker, "jc_mock_open_qa")
    assert out["accepted"] is True
    plan = await _plan(maker)
    assert plan["stage"] == "candidate_qa" and plan["candidate_qa"] is True
    assert plan["current_question_id"] is None


@pytest.mark.asyncio
async def test_opening_the_candidates_turn_twice_is_harmless(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    await _call(maker, "jc_mock_open_qa")
    again = await _call(maker, "jc_mock_open_qa")
    assert again["accepted"] is True


@pytest.mark.asyncio
async def test_no_new_question_is_asked_once_the_candidate_has_the_floor(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    await _call(maker, "jc_mock_open_qa")
    refused = await _ask(maker, STEMS[1])
    assert refused["accepted"] is False and refused["code"] == "candidate_qa_open"
    assert await _stem_count(maker, STEMS[1]) == 0
    assert (await _plan(maker))["asked_main"] == 1


@pytest.mark.asyncio
async def test_what_the_candidate_asks_is_never_recorded_as_an_answer(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    await _call(maker, "jc_mock_open_qa")
    async with maker() as db:
        assert await record_mock_answer(
            db, profile_id="p1", mock_session_id="ms1", text="团队有多少人，怎么分工？") is None


@pytest.mark.asyncio
async def test_the_candidates_turn_cannot_open_on_a_session_that_has_ended(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    await _call(maker, "jc_mock_end", {"reason": "user_ended"})
    out = await _call(maker, "jc_mock_open_qa")
    assert out["accepted"] is False and out["code"] == "session_closed"


# --- ending -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_interview_cannot_end_as_completed_before_the_candidate_has_had_a_turn(maker):
    await _open(maker)
    for stem in STEMS:
        await _ask(maker, stem)
    out = await _call(maker, "jc_mock_end", {"reason": "completed"})
    assert out["accepted"] is False and out["code"] == "candidate_qa_not_opened"
    assert "jc_mock_open_qa" in out["reason"]
    assert (await _plan(maker))["status"] == "active"


@pytest.mark.asyncio
async def test_it_ends_as_completed_once_the_candidate_has_had_a_turn(maker):
    await _open(maker)
    for stem in STEMS:
        await _ask(maker, stem)
    await _call(maker, "jc_mock_open_qa")
    out = await _call(maker, "jc_mock_end", {"reason": "completed"})
    assert out["accepted"] is True and out["ended_early"] is False


@pytest.mark.asyncio
async def test_uncovered_must_haves_are_reported_before_the_missing_turn(maker):
    await _open(maker, job_id="j1")
    await _ask(maker, STEMS[0])
    out = await _call(maker, "jc_mock_end", {"reason": "completed"})
    assert out["code"] == "uncovered"


@pytest.mark.asyncio
async def test_the_candidate_can_always_stop_without_the_turn(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    out = await _call(maker, "jc_mock_end", {"reason": "user_ended"})
    assert out["accepted"] is True and out["ended_early"] is True


# --- a question is checked before it is put -----------------------------------------------------


@pytest.mark.asyncio
async def test_a_question_a_page_long_is_refused_and_leaves_nothing(maker):
    await _open(maker)
    long_stem = "请你谈谈" + "这个问题" * 80
    out = await _ask(maker, long_stem)
    assert out["accepted"] is False and out["code"] == "stem_too_long"
    assert await _stem_count(maker, long_stem) == 0


@pytest.mark.asyncio
async def test_the_same_question_in_other_words_is_refused_and_names_the_earlier_one(maker):
    await _open(maker)
    await _ask(maker, "讲一个你拆分数据的经历")
    out = await _ask(maker, "讲一个你拆分数据库的经历")
    assert out["accepted"] is False and out["code"] == "too_similar"
    assert "讲一个你拆分数据的经历" in out["reason"]
    assert await _stem_count(maker, "讲一个你拆分数据库的经历") == 0


@pytest.mark.asyncio
async def test_a_different_question_is_accepted(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    assert (await _ask(maker, STEMS[1]))["accepted"] is True


@pytest.mark.asyncio
async def test_a_follow_up_may_resemble_the_question_it_follows(maker):
    await _open(maker)
    main = await _ask(maker, "讲一个你拆分数据的经历")
    close = "讲一个你拆分数据的经历，细说一下"
    # As a main question this is refused (it is the earlier one in other words)...
    assert (await _ask(maker, close))["code"] == "too_similar"
    # ...as a follow-up it is how the interviewer asks for more of the same story.
    follow = await _ask(maker, close, kind="followup", parent_question_id=main["question_id"])
    assert follow["accepted"] is True


@pytest.mark.asyncio
async def test_a_question_taken_from_a_bank_is_not_held_to_the_similarity_check(maker):
    # Only what the model makes up is checked; a bank question is already written and chosen.
    await _open(maker)
    await _ask(maker, "讲讲你的缓存设计思路")
    out = await _call(maker, "jc_mock_ask", {"question_id": "bank1"})
    assert out["accepted"] is True


@pytest.mark.asyncio
async def test_the_same_question_word_for_word_still_reads_as_already_asked(maker):
    await _open(maker)
    await _ask(maker, STEMS[0])
    out = await _ask(maker, STEMS[0] + "。")
    assert out["accepted"] is False and out["code"] == "already_asked"


def test_the_interviewer_holds_the_tool_for_the_candidates_turn():
    assert "jc_mock_open_qa" in require_skill("coach-mock").allowed_tools
