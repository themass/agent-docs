"""An interview is for the job the candidate is going for, whatever the job is.

The product knows fifteen lines of work. The guidance it had for each was about writing a résumé, so
a product manager's mock interview and a backend engineer's got the same instructions. These tests
pin the interview's own view of a family, how the family is decided, and that the interviewer and
the reviewer actually receive it."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.agent import subtask, turn
from jc.agent.standing_instructions import build_standing_block
from jc.agent.turn import TurnContext
from jc.coach.role_family import mock_role_family
from jc.db.base import Base
from jc.domain.role_families import GENERAL, PLAYBOOKS
from jc.models.interview import MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import interview_reviewer
from reviewer_agent_fake import FakeClientFactory, FakeReviewerAgent

#: Words that are about writing a résumé. An interviewer must never be told these.
RESUME_ONLY = ("Section priority", "resume is incomplete", "bullet", "简历", "Framing angles")
HEADING = "这场面试的岗位族"

FAMILIES = sorted(PLAYBOOKS)


def _prompt(skill, family):
    return build_standing_block(skill_id=skill, role_family=family, reply_language="zh-CN")


# --- the interview's view of a family ------------------------------------------


@pytest.mark.parametrize("skill", ["coach-mock", "interview-reviewer"])
@pytest.mark.parametrize("family", [f for f in FAMILIES if f != GENERAL])
def test_an_interview_prompt_names_the_family_and_what_to_probe_in_it(skill, family):
    prompt = _prompt(skill, family)
    playbook = PLAYBOOKS[family]
    assert playbook.label in prompt
    assert len(playbook.probe_angles) >= 2, family
    for angle in playbook.probe_angles:
        assert angle in prompt, (family, angle)


@pytest.mark.parametrize("skill", ["coach-mock", "interview-reviewer"])
@pytest.mark.parametrize("family", [f for f in FAMILIES if f != GENERAL])
def test_an_interview_prompt_carries_nothing_that_is_about_writing_a_resume(skill, family):
    prompt = _prompt(skill, family)
    # The skill text itself says "简历" when it reads the profile; only the family block is held to
    # this, so look at what comes after its heading.
    assert HEADING in prompt, (skill, family)
    block = prompt[prompt.index(HEADING):]
    for phrase in RESUME_ONLY:
        assert phrase not in block, (skill, family, phrase)


@pytest.mark.parametrize("family", FAMILIES)
def test_the_resume_skills_still_get_their_own_view_of_the_family(family):
    # Unchanged: the resume coach is still told how to write the résumé for this audience.
    prompt = _prompt("resume-coach", family)
    assert "Framing angles" in prompt and "Section priority" in prompt


def test_a_run_without_a_family_gets_no_family_block_at_all():
    for skill in ("coach-mock", "interview-reviewer"):
        assert HEADING not in _prompt(skill, None)


def test_the_general_family_has_nothing_specific_to_say_so_it_adds_no_block():
    assert PLAYBOOKS[GENERAL].probe_angles == ()
    for skill in ("coach-mock", "interview-reviewer"):
        assert HEADING not in _prompt(skill, GENERAL)


def test_how_an_outcome_is_measured_and_what_it_is_about_are_in_the_interview_view():
    prompt = _prompt("coach-mock", "pm")
    assert "留存与活跃" in prompt and "功能模块" in prompt


# --- which family the interview is for -----------------------------------------


def test_the_job_decides_before_the_candidates_past_titles():
    assert mock_role_family(job_title="产品经理", profile_titles=("后端工程师",)) == "pm"


def test_a_stored_job_category_decides_before_its_title():
    assert mock_role_family(job_category="operations", job_title="产品经理") == "operations"


def test_with_no_job_the_candidates_own_titles_decide():
    assert mock_role_family(job_title=None, profile_titles=("市场经理", "运营专员")) == "marketing"


def test_nothing_recognisable_is_the_general_family_not_a_guess():
    assert mock_role_family(job_title="某某专员", profile_titles=("某某",)) == GENERAL
    assert mock_role_family() == GENERAL


@pytest.mark.parametrize(
    ("title", "family"),
    [("高级产品经理", "pm"), ("用户增长运营", "operations"), ("UI设计师", "design"),
     ("大客户销售", "sales"), ("招聘经理", "hr"), ("财务分析师", "finance"),
     ("法务专员", "legal"), ("后端开发工程师", "backend")],
)
def test_the_usual_job_titles_of_each_line_of_work_are_recognised(title, family):
    assert mock_role_family(job_title=title) == family


# --- the interviewer and the reviewer are given it -----------------------------


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/family.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user", version=1, payload={
            "experiences": [{"id": "e1", "company": "某公司", "title": "后端工程师",
                             "start_date": "2019-01", "end_date": "2024-01"}]}))
        db.add(Job(id="j_pm", profile_id="p1", company="示例", title="产品经理", raw_text="岗位",
                   tag="warmup", fit_gaps=[], fit_blockers=[], status="active",
                   requirements={"must_have_skills": []}))
        db.add(Job(id="j_none", profile_id="p1", company="示例", title="某某专员", raw_text="岗位",
                   tag="warmup", fit_gaps=[], fit_blockers=[], status="active",
                   requirements={"must_have_skills": []}))
        # Titled like a product job, but stored under the operations category.
        db.add(Job(id="j_cat", profile_id="p1", company="示例", title="产品经理", raw_text="岗位",
                   role_category="operations", tag="warmup", fit_gaps=[], fit_blockers=[],
                   status="active", requirements={"must_have_skills": []}))
        db.add(Profile(id="p2", user_id="u1", owner_kind="user", payload={}, version=1))
        await db.flush()
        # Another profile's job: a product job that this profile's session must not read.
        db.add(Job(id="j_theirs", profile_id="p2", company="别家", title="销售经理",
                   raw_text="岗位", tag="warmup", fit_gaps=[], fit_blockers=[],
                   status="active", requirements={"must_have_skills": []}))
        await db.commit()
    yield makers
    await engine.dispose()


async def _session(maker, job_id):
    async with maker() as db:
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id=job_id,
            question_ids=[], bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="standard", level="mid", coverage={"asked": []},
        ))
        await db.commit()


async def _facts(maker):
    async with maker() as db:
        ctx = TurnContext(db=db, profiles=None, actor=None, profile_id="p1", job_id=None,
                          ui_context=SimpleNamespace(mock_session_id="ms1"),
                          default_skill="coach-mock")
        return await turn.TURN_PROVIDERS["mock_session"].gather(ctx)


@pytest.mark.asyncio
async def test_a_backend_engineer_going_for_a_product_job_is_interviewed_as_a_product_manager(
    maker,
):
    await _session(maker, "j_pm")
    assert (await _facts(maker))["role_family"] == "pm"


@pytest.mark.asyncio
async def test_a_job_that_cannot_be_placed_falls_back_to_the_candidates_own_work(maker):
    await _session(maker, "j_none")
    assert (await _facts(maker))["role_family"] == "backend"


@pytest.mark.asyncio
async def test_a_session_with_no_job_uses_the_candidates_own_work(maker):
    await _session(maker, None)
    assert (await _facts(maker))["role_family"] == "backend"


@pytest.mark.asyncio
async def test_the_reviewer_is_started_with_the_family_of_the_interview(maker, monkeypatch):
    await _session(maker, "j_pm")
    async with maker() as db:
        row = await db.get(MockSession, "ms1")
        row.status = "completed"
        await db.commit()
    agent = FakeReviewerAgent(maker, report=None)
    monkeypatch.setattr(subtask, "get_deerflow_client", FakeClientFactory(agent))
    async with maker() as db:
        await interview_reviewer.review_session(
            db, user_id="u1", profile_id="p1", mock_session_id="ms1")
    assert agent.runs[0]["metadata"].extra["role_family"] == "pm"


@pytest.mark.asyncio
async def test_a_stored_category_on_the_job_beats_the_jobs_title(maker):
    await _session(maker, "j_cat")
    assert (await _facts(maker))["role_family"] == "operations"


@pytest.mark.asyncio
async def test_a_job_of_another_profile_does_not_decide_the_family(maker):
    # j_theirs is a sales job under profile p2. Reading it would make this interview a sales one.
    await _session(maker, "j_theirs")
    assert (await _facts(maker))["role_family"] == "backend"
