"""What the reviewer and the report read of a session: the turns, in the order they were asked, with
the follow-ups marked as follow-ups of a main question.

The reviewer used to get a flat list of question ids in the order they were first filed, with the
follow-ups at the same level as the main questions, and any question drawn from the bank but never
asked among them. These tests pin the shape it gets now."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.authz.scope import RunScope
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.interview_service import InterviewService
from jc.services.mock_report_service import session_transcript, write_report
from jc.services.mock_turns import session_turns
from jc.services.question_bank_service import mock_session_history
from jc.stores.interview_store import InterviewStore

OWNER = UserActor(user_id="u1", session_id="s")
A1 = "我把结算接口拆成了两张表，耗时三周。"
A2 = "靠双写加每晚的对账任务保证两边一致。"
A3 = "那次是缓存雪崩，我们加了互斥锁。"
MAIN1 = {"question_id": "q1", "kind": "main", "parent_question_id": None}
FOLLOW1 = {"question_id": "q2", "kind": "followup", "parent_question_id": "q1"}
MAIN2 = {"question_id": "q3", "kind": "main", "parent_question_id": None}
SKIPPED = {"question_id": "q4", "kind": "main", "parent_question_id": None, "skipped": True}


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/turns.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user",
                       payload={"experience": "结算接口拆表 对账任务 缓存雪崩"}, version=1))
        for qid, stem in (("q1", "讲一个你拆分数据的经历"), ("q2", "拆表时怎么保证数据一致"),
                          ("q3", "讲一次线上故障"), ("q4", "讲一个失败的项目"),
                          ("q5", "题库里抽到但没有问的题")):
            db.add(InterviewQuestion(id=qid, profile_id="p1", stem=stem,
                                     question_type="behavioral"))
        for aid, qid, text in (("a1", "q1", A1), ("a2", "q2", A2), ("a3", "q3", A3)):
            db.add(AnswerAttempt(id=aid, question_id=qid, profile_id="p1", mock_session_id="ms1",
                                 user_answer=text, coach_feedback={}, reference_answer=None))
        await db.commit()
    yield makers
    await engine.dispose()


async def _session(maker, *, asked=None, question_ids=None, status="completed", quota=True):
    coverage = {"asked": asked} if asked is not None else None
    async with maker() as db:
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target",
            question_ids=question_ids if question_ids is not None else [], bank_draw_count=0,
            generated_count=0, status=status, started_at=datetime(2026, 11, 5, tzinfo=UTC),
            completed_at=datetime(2026, 11, 5, 1, tzinfo=UTC), style="standard", level="mid",
            quota_counted=quota, coverage=coverage, report_status="queued",
        ))
        await db.commit()


async def _turns(maker):
    async with maker() as db:
        store = InterviewStore(db)
        return await session_turns(store, await store.get_mock_session("ms1"))


@pytest.mark.asyncio
async def test_turns_follow_the_order_the_questions_were_asked(maker):
    # q5 was drawn from the bank at the start and never asked; q3 was filed before q2.
    await _session(maker, question_ids=["q5", "q1", "q3", "q2"],
                   asked=[MAIN1, FOLLOW1, MAIN2])
    turns = await _turns(maker)
    assert [t.question_id for t in turns] == ["q1", "q2", "q3"]


@pytest.mark.asyncio
async def test_a_follow_up_is_marked_with_its_main_question(maker):
    await _session(maker, question_ids=["q1", "q2"], asked=[MAIN1, FOLLOW1])
    main, follow = await _turns(maker)
    assert (main.kind, main.parent_question_id) == ("main", None)
    assert (follow.kind, follow.parent_question_id) == ("followup", "q1")
    assert (main.answer, follow.answer) == (A1, A2)
    assert follow.stem == "拆表时怎么保证数据一致"


@pytest.mark.asyncio
async def test_a_skipped_question_stays_in_the_turns_with_no_answer(maker):
    await _session(maker, question_ids=["q1", "q4"], asked=[MAIN1, SKIPPED])
    turns = await _turns(maker)
    assert [(t.question_id, t.skipped, t.answer) for t in turns] == [
        ("q1", False, A1), ("q4", True, "")]


@pytest.mark.asyncio
async def test_a_session_with_no_asked_list_reads_every_question_as_a_main_question(maker):
    # Sessions from before the guards recorded nothing but the question ids.
    await _session(maker, question_ids=["q1", "q3"], asked=None)
    turns = await _turns(maker)
    assert [(t.question_id, t.kind, t.parent_question_id) for t in turns] == [
        ("q1", "main", None), ("q3", "main", None)]


@pytest.mark.asyncio
async def test_the_report_transcript_keeps_its_old_keys_and_adds_the_new_ones(maker):
    await _session(maker, question_ids=["q1", "q2"], asked=[MAIN1, FOLLOW1])
    async with maker() as db:
        store = InterviewStore(db)
        transcript = await session_transcript(store, await store.get_mock_session("ms1"))
    assert transcript[1] == {"question_id": "q2", "stem": "拆表时怎么保证数据一致",
                             "answer": A2, "kind": "followup", "parent_question_id": "q1",
                             "skipped": False, "tags": []}


@pytest.mark.asyncio
async def test_the_history_the_reviewer_reads_marks_follow_ups_and_skips(maker):
    await _session(maker, question_ids=["q5", "q1", "q2", "q4"],
                   asked=[MAIN1, FOLLOW1, SKIPPED])
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        out = await mock_session_history(scope, mock_session_id="ms1")
    assert [(t["question_id"], t["kind"], t["parent_question_id"], t["skipped"])
            for t in out["turns"]] == [
        ("q1", "main", None, False), ("q2", "followup", "q1", False), ("q4", "main", None, True)]
    assert out["turns"][1]["user_answer"] == A2
    assert out["turns"][2]["user_answer"] is None


# --- the report: follow-ups are evidence for their main question ---------------------------------


def _raw(question_id, evidence_quote):
    return {"questions": [{"question_id": question_id, "scores": {"depth": 7},
                           "evidence": {"depth": evidence_quote}}]}


async def _write(maker, raw):
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        return await write_report(scope, mock_session_id="ms1", raw=raw)


@pytest.mark.asyncio
async def test_a_quote_from_a_follow_up_answer_is_evidence_for_its_main_question(maker):
    await _session(maker, question_ids=["q1", "q2"], asked=[MAIN1, FOLLOW1])
    out = await _write(maker, _raw("q1", "每晚的对账任务"))
    assert out["overall"]["depth"] == 7.0
    assert out["checks"]["rejected_evidence"] == 0


@pytest.mark.asyncio
async def test_a_quote_from_another_main_question_is_still_not_evidence(maker):
    await _session(maker, question_ids=["q1", "q2", "q3"], asked=[MAIN1, FOLLOW1, MAIN2])
    out = await _write(maker, _raw("q1", "缓存雪崩"))
    assert out["overall"]["depth"] is None
    assert out["checks"]["rejected_evidence"] == 1


@pytest.mark.asyncio
async def test_scoring_a_follow_up_directly_is_refused_with_what_to_do_instead(maker):
    await _session(maker, question_ids=["q1", "q2"], asked=[MAIN1, FOLLOW1])
    with pytest.raises(ValueError) as exc:
        await _write(maker, _raw("q2", "对账任务"))
    assert "追问" in str(exc.value) and "q1" in str(exc.value)


@pytest.mark.asyncio
async def test_a_question_that_was_not_asked_cannot_be_scored(maker):
    await _session(maker, question_ids=["q5", "q1"], asked=[MAIN1])
    with pytest.raises(ValueError, match="not part of this session"):
        await _write(maker, _raw("q5", "x"))


@pytest.mark.asyncio
async def test_the_report_page_nests_follow_ups_under_their_main_question(maker):
    await _session(maker, question_ids=["q1", "q2", "q3"], asked=[MAIN1, FOLLOW1, MAIN2])
    await _write(maker, {"questions": [
        {"question_id": "q1", "scores": {"depth": 7}, "evidence": {"depth": "对账任务"}},
        {"question_id": "q3", "scores": {"depth": 5}, "evidence": {"depth": "互斥锁"}},
    ]})
    async with maker() as db:
        service = InterviewService(db)
        async with db.begin_nested():
            session = await db.get(MockSession, "ms1")
            session.report_status = "ready"
        out = await service.get_mock_report("ms1", actor=OWNER)
    assert out.status == "ready"
    assert [q.question_id for q in out.questions] == ["q1", "q3"]
    assert out.questions[0].answer == A1
    assert [(f.question_id, f.stem, f.answer) for f in out.questions[0].follow_ups] == [
        ("q2", "拆表时怎么保证数据一致", A2)]
    assert out.questions[1].follow_ups == []


# --- the reviewer runs after the session has ended --------------------------------------------


@pytest.mark.asyncio
async def test_the_reviewer_can_read_the_history_of_a_session_that_has_ended(maker):
    # The reviewer is started once the session is completed. A history call that refuses a
    # completed session leaves it with nothing to review.
    from jc.mcp.handlers import dispatch_tool

    await _session(maker, question_ids=["q1", "q2"], asked=[MAIN1, FOLLOW1], status="completed")
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        out = await dispatch_tool(scope, "jc_mock_session_history", {"mock_session_id": "ms1"})
    assert out["status"] == "completed"
    assert [t["question_id"] for t in out["turns"]] == ["q1", "q2"]
    assert out["turns"][0]["user_answer"] == A1


@pytest.mark.asyncio
async def test_the_history_of_another_profiles_session_is_still_refused(maker):
    from jc.mcp.handlers import dispatch_tool

    await _session(maker, question_ids=["q1"], asked=[MAIN1], status="completed")
    async with maker() as db:
        db.add(Profile(id="p2", user_id="u1", owner_kind="user", payload={}, version=1))
        await db.commit()
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p2", mock_session_id="ms1")
        with pytest.raises(PermissionError):
            await dispatch_tool(scope, "jc_mock_session_history", {"mock_session_id": "ms1"})


@pytest.mark.asyncio
async def test_a_run_bound_to_one_session_cannot_read_another(maker):
    from jc.mcp.handlers import dispatch_tool

    await _session(maker, question_ids=["q1"], asked=[MAIN1], status="completed")
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms_other")
        with pytest.raises(PermissionError):
            await dispatch_tool(scope, "jc_mock_session_history", {"mock_session_id": "ms1"})
