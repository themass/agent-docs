"""Where questions and their reference material come from, and what the reviewer reads of a session.

The question bank and the profile library are not built yet. They plug in here: a source returns
candidate questions, and may know the reference material for a question (what a strong answer
shows). Nothing downstream changes when one is added, and these tests use a stand-in to show it."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.coach import sources
from jc.coach.sources import QuestionCandidate, QuestionReference, SearchRequest
from jc.db.base import Base
from jc.mcp.handlers import dispatch_tool
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User

STEM = "讲一个你拆分数据的经历"
RAW_JD = "负责结算系统。" + "详细职责。" * 800


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/sources.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表"}, version=1))
        db.add(Job(id="j1", profile_id="p1", company="示例科技", title="后端工程师",
                   raw_text=RAW_JD, tag="warmup", fit_gaps=[], fit_blockers=[], status="active",
                   requirements={"must_have_skills": ["Python", "分布式事务"],
                                 "nice_to_have_skills": ["Kafka"], "seniority": "senior"}))
        db.add(InterviewQuestion(id="q1", profile_id="p1", stem=STEM, question_type="behavioral",
                                 tags=["数据"]))
        db.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
                             user_answer="我把结算接口拆成了两张表。", coach_feedback={},
                             reference_answer=None))
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id="j1",
            question_ids=["q1"], bank_draw_count=0, generated_count=0, status="completed",
            started_at=datetime(2026, 11, 5, tzinfo=UTC), style="pressure", level="senior",
            coverage={"asked": [{"question_id": "q1", "kind": "main",
                                 "parent_question_id": None}]},
        ))
        await db.commit()
    yield makers
    await engine.dispose()


@pytest.fixture(autouse=True)
def _clean_registry():
    saved = list(sources.registered())
    yield
    sources.reset(saved)


class _FakeBank:
    """A stand-in for a curated bank: it knows a question by its text and has reference material."""

    name = "fake-bank"

    async def search(self, scope, request: SearchRequest) -> list[QuestionCandidate]:
        return [QuestionCandidate(stem="讲一次线上故障", question_type="behavioral",
                                  source=self.name, tags=["运维"], difficulty="medium",
                                  reference_key="fb-1")]

    async def reference(self, scope, *, stem: str, question_id: str):
        if stem != STEM:
            return None
        return QuestionReference(
            source=self.name,
            strong="时间线清楚，说明排查路径，区分本人和团队的贡献。",
            adequate="讲了故障和修复，但复盘含糊。",
            weak="从现象直接跳到结论。",
            follow_ups=["你先排除了什么？"],
            signals_positive=["解释排查思路"],
            signals_negative=["说不出排查步骤"],
        )


async def _call(maker, name, arguments):
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        return await dispatch_tool(scope, name, arguments)


# --- the registry ------------------------------------------------------------------------------


def test_the_personal_bank_is_the_only_source_until_another_registers():
    assert [s.name for s in sources.registered()] == ["personal"]


def test_a_source_registers_once_and_can_be_replaced_by_name():
    sources.register(_FakeBank())
    sources.register(_FakeBank())
    assert [s.name for s in sources.registered()] == ["personal", "fake-bank"]


# --- searching ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_search_with_only_the_personal_bank_looks_as_it_always_did(maker):
    out = await _call(maker, "jc_bank_search_questions", {"query": "拆分"})
    assert [q["id"] for q in out["questions"]] == ["q1"]
    assert out["questions"][0]["stem"] == STEM
    assert out["questions"][0]["source"] == "personal"


@pytest.mark.asyncio
async def test_a_registered_source_is_searched_too_and_its_questions_say_where_they_came_from(
    maker,
):
    sources.register(_FakeBank())
    out = await _call(maker, "jc_bank_search_questions", {"query": "故障"})
    stems = {q["stem"]: q for q in out["questions"]}
    assert stems["讲一次线上故障"]["source"] == "fake-bank"
    assert stems["讲一次线上故障"]["id"] is None
    assert stems["讲一次线上故障"]["difficulty"] == "medium"


@pytest.mark.asyncio
async def test_a_source_that_breaks_does_not_break_the_search(maker):
    class Broken:
        name = "broken"

        async def search(self, scope, request):
            raise RuntimeError("index offline")

    sources.register(Broken())
    out = await _call(maker, "jc_bank_search_questions", {"query": "拆分"})
    assert [q["id"] for q in out["questions"]] == ["q1"]


@pytest.mark.asyncio
async def test_the_same_question_from_two_sources_is_listed_once(maker):
    class Echo:
        name = "echo"

        async def search(self, scope, request):
            return [QuestionCandidate(stem=STEM, question_type="behavioral", source="echo")]

    sources.register(Echo())
    out = await _call(maker, "jc_bank_search_questions", {"query": "拆分"})
    assert [q["stem"] for q in out["questions"]].count(STEM) == 1
    assert out["questions"][0]["source"] == "personal"


# --- what the reviewer reads -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_history_tells_the_reviewer_the_job_the_level_and_the_style(maker):
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    assert out["style"] == "pressure"
    assert out["level"]["key"] == "senior" and out["level"]["benchmark"] == "P7"
    assert out["level"]["requirement"] and out["level"]["depth"]
    job = out["job"]
    assert (job["company"], job["title"]) == ("示例科技", "后端工程师")
    assert job["must_have"] == ["Python", "分布式事务"] and job["nice_to_have"] == ["Kafka"]
    assert job["seniority"] == "senior"


@pytest.mark.asyncio
async def test_the_job_text_is_clipped_and_marked_as_data(maker):
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    job = out["job"]
    assert len(job["description"]) <= 3000
    assert job["description"].startswith("负责结算系统")
    assert "数据" in job["note"] and "指令" in job["note"]


@pytest.mark.asyncio
async def test_a_job_of_another_profile_is_never_handed_to_the_reviewer(maker):
    # A session that points at a job in someone else's profile must not carry that job's text.
    async with maker() as db:
        db.add(Profile(id="p2", user_id="u1", owner_kind="user", payload={}, version=1))
        await db.flush()
        db.add(Job(id="j_other", profile_id="p2", company="别家公司", title="秘密岗位",
                   raw_text="别的档案里的岗位描述", tag="warmup", fit_gaps=[], fit_blockers=[],
                   status="active", requirements={"must_have_skills": ["保密"]}))
        session = await db.get(MockSession, "ms1")
        session.job_id = "j_other"
        await db.commit()
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    assert out["job"] is None
    assert "别家公司" not in str(out) and "秘密岗位" not in str(out)


@pytest.mark.asyncio
async def test_a_session_from_before_levels_and_jobs_still_has_a_history(maker):
    async with maker() as db:
        session = await db.get(MockSession, "ms1")
        session.level, session.job_id = None, None
        await db.commit()
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    assert out["level"] is None and out["job"] is None
    assert len(out["turns"]) == 1


@pytest.mark.asyncio
async def test_a_turn_carries_reference_material_when_a_source_has_it(maker):
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    assert out["turns"][0]["reference"] is None

    sources.register(_FakeBank())
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    reference = out["turns"][0]["reference"]
    assert reference["source"] == "fake-bank"
    assert reference["strong"].startswith("时间线清楚")
    assert reference["follow_ups"] == ["你先排除了什么？"]


@pytest.mark.asyncio
async def test_a_reference_source_that_breaks_leaves_the_history_readable(maker):
    class Broken:
        name = "broken"

        async def search(self, scope, request):
            return []

        async def reference(self, scope, *, stem, question_id):
            raise RuntimeError("index offline")

    sources.register(Broken())
    out = await _call(maker, "jc_mock_session_history", {"mock_session_id": "ms1"})
    assert out["turns"][0]["user_answer"] == "我把结算接口拆成了两张表。"
    assert out["turns"][0]["reference"] is None
