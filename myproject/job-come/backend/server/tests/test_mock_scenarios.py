"""ADR-008 scenarios S1–S10: each one is a sequence of candidate messages, and the test checks the
whole reply sequence and the ledger at the end. The model is a stub; the database is SQLite."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models.enums import MockSessionStatus
from jc.models.interview import InterviewQuestion, MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.services import mock_interview_flow as flow
from jc.services.mock_answer_recorder import record_mock_answer
from jc.stores.interview_store import InterviewStore

MUST_HAVE = ["Python", "分布式事务"]
STEMS = {
    "q01": "讲一个你用 Python 写过的数据脚本",
    "q02": "你如何处理分布式事务的一致性",
    "q03": "讲讲你做过的一件事的取舍",
    "q04": "讲讲你做过的另一件事的取舍",
    "q05": "讲讲你做过的第三件事的取舍",
}
ANSWER = "我们把结算拆成两张表，样本量按每组五千人来定，耗时三周。"


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/turn.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await session.flush()
        session.add(Profile(id="p1", user_id="u1", owner_kind="user",
                            payload={"experience": "结算"}, version=1))
        session.add(Job(id="j1", profile_id="p1", company="示例", title="后端", raw_text="岗位",
                        requirements={"must_have_skills": MUST_HAVE}))
        for qid, stem in STEMS.items():
            session.add(InterviewQuestion(id=qid, profile_id="p1", job_id="j1", stem=stem,
                                          question_type="behavioral"))
        # Not counted against the quota: the warm-up limits (5 main questions, 1 follow-up) apply.
        session.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", job_id="j1",
            question_ids=[], bank_draw_count=0, generated_count=0, status="active",
            started_at=datetime.now(UTC), style="pressure", quota_counted=False,
        ))
        await session.commit()
    yield maker
    await engine.dispose()


class Model:
    """Stands in for the model. `followup` is the judgement it gives next."""

    def __init__(self):
        self.followup: dict = {"followup": False, "question": "", "quotes": []}
        self.calls: list[str] = []

    async def __call__(self, skill_id, payload, caller):
        self.calls.append(payload["task"])
        if payload["task"] == "followup":
            return self.followup
        if payload["task"] == "answer":
            return {"answer": "团队五个人，在杭州。"}
        if payload["task"] == "stem":
            return {"question": f"你在{payload['requirement']}上做过哪件事？"}
        return {"question": payload["question"]}


@pytest.fixture
def model(monkeypatch):
    fake = Model()
    monkeypatch.setattr(flow, "_model_json", fake)
    return fake


async def _turn(maker, text: str) -> str | None:
    async with maker() as db:
        answered = await record_mock_answer(
            db, profile_id="p1", mock_session_id="ms1", text=text,
        )
        return await flow.run_turn(
            db, user_id="u1", profile_id="p1", mock_session_id="ms1",
            text=text, answered=answered is not None,
        )


async def _coverage(maker) -> dict:
    async with maker() as db:
        return dict((await InterviewStore(db).get_mock_session("ms1")).coverage or {})




async def test_S1_a_full_interview_ends_completed_with_the_candidates_turn(db, model):
    assert "面试官" in await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    for _ in range(5):
        assert await _turn(db, ANSWER)
    assert await _turn(db, "团队多大？") == "团队五个人，在杭州。"
    assert await _turn(db, "结束") == flow.CLOSING_TEXT
    async with db() as session:
        row = await InterviewStore(session).get_mock_session("ms1")
        assert row.status == MockSessionStatus.COMPLETED.value
    state = await _coverage(db)
    assert len([a for a in state["asked"] if a["kind"] == "main"]) == 5


async def test_S2_a_skip_says_the_line_and_asks_a_new_question(db, model):
    await _turn(db, "你好")
    first = await _turn(db, "我叫张三。")
    skipped_question = first.split("\n")[-1]
    reply = await _turn(db, "下一题")
    assert reply.startswith(flow.SKIP_TEXT)
    assert reply.split("\n")[-1] != skipped_question
    state = await _coverage(db)
    assert state["asked"][0]["skipped"] is True


async def test_S3_skipping_a_follow_up_closes_its_main_and_no_second_follow_up(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    model.followup = {"followup": True, "question": "样本量是怎么算出来的？",
                      "quotes": ["样本量按每组五千人来定"]}
    assert await _turn(db, ANSWER) == "样本量是怎么算出来的？"
    calls_before = len(model.calls)
    reply = await _turn(db, "下一题")
    assert reply.startswith(flow.SKIP_TEXT)
    assert "followup" not in model.calls[calls_before:]
    state = await _coverage(db)
    mains_open = [a for a in state["asked"] if a["kind"] == "main" and not a.get("skipped")]
    assert state["asked"][-1]["kind"] == "main"
    assert mains_open  # the interview went on to a new main question


async def test_S4_repeat_says_the_question_again_and_records_nothing(db, model):
    await _turn(db, "你好")
    second = await _turn(db, "我叫张三。")
    question = second.split("\n")[-1]
    before = await _coverage(db)
    assert await _turn(db, "没听清，能再说一遍吗") == question
    assert await _coverage(db) == before


async def test_S5_an_answer_then_end_closes_without_another_question(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    await _turn(db, ANSWER)
    assert await _turn(db, "结束") == flow.CLOSING_TEXT
    async with db() as session:
        row = await InterviewStore(session).get_mock_session("ms1")
        assert row.status == MockSessionStatus.COMPLETED.value


async def test_S6_a_bank_question_that_points_back_is_never_offered(db, model):
    async with db() as session:
        session.add(InterviewQuestion(id="qback", profile_id="p1", job_id="j1",
                                      stem="上一题你提到支付相关的写操作，怎么防重？",
                                      question_type="behavioral"))
        await session.commit()
    await _turn(db, "你好")
    reply = await _turn(db, "我叫张三。")
    assert "上一题你提到" not in reply
    state = await _coverage(db)
    assert "qback" not in [a["question_id"] for a in state["asked"]]


async def test_S7_a_follow_up_quoting_nothing_from_the_answer_is_dropped(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    model.followup = {"followup": True, "question": "样本量怎么定的？",
                      "quotes": ["我们做过很多实验"]}
    reply = await _turn(db, ANSWER)
    assert "样本量" not in reply
    state = await _coverage(db)
    assert all(a["kind"] == "main" for a in state["asked"])


async def test_S8_a_slow_model_falls_back_to_the_bank_text(db, monkeypatch):
    """A model call that returns nothing (timed out) never blocks the flow: no follow-up, the next
    main question, from the bank's own text."""
    async def nothing(skill_id, payload, caller):
        return None

    monkeypatch.setattr(flow, "_model_json", nothing)
    await _turn(db, "你好")
    reply = await _turn(db, "我叫张三。")
    assert reply.split("\n")[-1] in STEMS.values()
    reply2 = await _turn(db, ANSWER)
    assert reply2 and not reply2.startswith(flow.SKIP_TEXT)


async def test_S9_a_command_in_the_candidates_turn_closes_the_interview(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    for _ in range(5):
        await _turn(db, ANSWER)
    assert await _turn(db, "团队多大？") == "团队五个人，在杭州。"
    assert await _turn(db, "下一题") == flow.CLOSING_TEXT


async def test_S10_a_candidate_answer_with_a_question_mark_is_replaced_by_the_referral(
    db, monkeypatch,
):
    async def asks_back(skill_id, payload, caller):
        if payload["task"] == "answer":
            return {"answer": "团队多大你想了解什么？"}
        return {"question": payload.get("question", "")}

    monkeypatch.setattr(flow, "_model_json", asks_back)
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    for _ in range(5):
        await _turn(db, ANSWER)
    assert await _turn(db, "团队多大？") == flow.REFER_TEXT
