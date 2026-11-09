"""The server-driven interview (ADR-007): each turn's reply is decided and written by the server.

The model is replaced by a script per test. What is checked: the reply text, what is recorded in the
ledger, and that the model's output is used only when it passes its checks."""

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


async def test_the_first_message_gets_the_server_opening_and_nothing_is_recorded(db, model):
    reply = await _turn(db, "你好")
    assert "面试官" in reply and "自我介绍" in reply
    state = await _coverage(db)
    assert state["opening_sent"] is True
    assert state.get("asked") in (None, [])
    assert model.calls == []  # the model is not involved


async def test_the_self_introduction_is_not_an_answer_and_the_first_question_follows(db, model):
    await _turn(db, "你好")
    reply = await _turn(db, "我叫张三，做了六年后端。")
    assert reply.startswith("好，谢谢你的介绍。")
    assert "Python" in reply  # the first uncovered must-have is asked first
    state = await _coverage(db)
    assert [a["question_id"] for a in state["asked"]] == ["q01"]
    assert state["asked"][0]["kind"] == "main"


async def test_an_answer_gets_a_follow_up_when_the_model_quotes_the_candidate(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    model.followup = {"followup": True, "question": "样本量是怎么算出来的？",
                      "quotes": ["样本量按每组五千人来定"]}
    reply = await _turn(db, ANSWER)
    assert reply == "样本量是怎么算出来的？"
    state = await _coverage(db)
    last = state["asked"][-1]
    assert last["kind"] == "followup" and last["parent_question_id"] == "q01"


async def test_a_follow_up_that_quotes_nothing_is_dropped_and_the_next_main_is_asked(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    model.followup = {"followup": True, "question": "样本量是怎么算出来的？",
                      "quotes": ["我们做过很多实验"]}  # not in the answer: invented
    reply = await _turn(db, ANSWER)
    assert "样本量" not in reply
    state = await _coverage(db)
    assert all(a["kind"] == "main" for a in state["asked"])
    assert "q01" in state["closed_mains"]


async def test_skip_moves_on_with_a_short_line_and_records_nothing_as_an_answer(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    reply = await _turn(db, "下一题")
    assert reply.startswith("好，我们换一题。")
    state = await _coverage(db)
    assert state["asked"][0]["skipped"] is True
    assert "q01" in state["closed_mains"]


async def test_a_request_to_end_ends_the_session_with_the_closing_line(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    reply = await _turn(db, "我想结束这场面试")
    assert "谢谢你的时间" in reply
    async with db() as session:
        assert (await InterviewStore(session).get_mock_session("ms1")).status == \
            MockSessionStatus.COMPLETED.value


async def test_repeat_request_says_the_question_again_and_records_nothing(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    reply = await _turn(db, "没听清，能再说一遍吗")
    assert reply == STEMS["q01"]
    state = await _coverage(db)
    assert state.get("answered_upto", 0) == 0


async def test_the_full_run_reaches_candidate_questions_after_the_main_limit(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    # Four answers each bring the next main question; the fifth answers the fifth and the
    # interview has no main question left, so it turns to the candidate.
    for _ in range(4):
        assert await _turn(db, ANSWER)
    reply = await _turn(db, ANSWER)
    assert reply == flow.QA_OPEN_TEXT
    state = await _coverage(db)
    assert state["candidate_qa"] is True
    assert len([a for a in state["asked"] if a["kind"] == "main"]) == 5
    # The candidate's questions: the model writes a short answer, checked. Nothing is recorded.
    assert await _turn(db, "公司团队多大？") == "团队五个人，在杭州。"


async def test_a_wording_that_points_back_is_replaced_by_the_bank_text(db, model, monkeypatch):
    async def bad_phrase(skill_id, payload, caller):
        return {"question": "你刚说的分布式事务是怎么做的？"}

    monkeypatch.setattr(flow, "_model_json", bad_phrase)
    await _turn(db, "你好")
    reply = await _turn(db, "我叫张三。")
    assert reply == "好，谢谢你的介绍。\n" + STEMS["q01"]


async def test_another_jobs_questions_are_never_put_to_this_candidate(db, model, monkeypatch):
    """The job has no bank questions of its own: the server writes its own, and borrows none."""
    async with db() as session:
        session.add(InterviewQuestion(id="other1", profile_id="p1", job_id="j2",
                                      stem="你做过的增长实验是怎么设计的？",
                                      question_type="behavioral"))
        await session.execute(__import__("sqlalchemy").delete(InterviewQuestion).where(
            InterviewQuestion.job_id == "j1"))
        await session.commit()
    await _turn(db, "你好")
    reply = await _turn(db, "我叫张三。")
    assert "增长实验" not in reply
    assert "Python" in reply  # the first uncovered must-have gets a question of its own
    state = await _coverage(db)
    first = state["asked"][0]["question_id"]
    async with db() as session:
        written = await InterviewStore(session).get_question(first)
        assert written.job_id == "j1" and written.tags == ["Python"]


async def test_a_generated_stem_without_the_requirement_is_refused(db, monkeypatch):
    async def off_topic(skill_id, payload, caller):
        if payload["task"] == "answer":
            return {"answer": "团队五个人，在杭州。"}
        if payload["task"] == "stem":
            return {"question": "讲讲你最喜欢的一部电影？"}
        return {"question": payload.get("question", "")}

    monkeypatch.setattr(flow, "_model_json", off_topic)
    await _turn(db, "你好")
    async with db() as session:
        session.execute  # noqa: B018 - the pool is emptied below
        from sqlalchemy import delete
        await session.execute(delete(InterviewQuestion).where(InterviewQuestion.job_id == "j1"))
        await session.commit()
    reply = await _turn(db, "我叫张三。")
    assert reply.endswith(flow.NO_QUESTIONS_TEXT)
    async with db() as session:
        row = await InterviewStore(session).get_mock_session("ms1")
        assert row.status == MockSessionStatus.COMPLETED.value


async def test_a_candidate_question_gets_a_checked_answer(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    for _ in range(5):
        await _turn(db, ANSWER)
    await _turn(db, ANSWER)  # the floor opens to the candidate
    assert await _turn(db, "团队多大？") == "团队五个人，在杭州。"


async def test_an_answer_that_asks_back_is_replaced_by_the_referral(db, model, monkeypatch):
    async def asks_back(skill_id, payload, caller):
        return {"answer": "团队多大你想了解什么？"}

    monkeypatch.setattr(flow, "_model_json", asks_back)
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    for _ in range(5):
        await _turn(db, ANSWER)
    await _turn(db, ANSWER)
    assert await _turn(db, "团队多大？") == flow.REFER_TEXT


async def test_a_steering_word_in_the_candidates_turn_closes_the_interview(db, model):
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    for _ in range(5):
        await _turn(db, ANSWER)
    await _turn(db, ANSWER)
    assert await _turn(db, "下一题") == flow.CLOSING_TEXT
    async with db() as session:
        row = await InterviewStore(session).get_mock_session("ms1")
        assert row.status == MockSessionStatus.COMPLETED.value


def test_back_references_are_recognised_however_they_open():
    from jc.services.interview_reply import refers_to_earlier_talk

    assert refers_to_earlier_talk("上一题你提到支付相关的写操作带唯一约束防重。那往大了说呢？")
    assert refers_to_earlier_talk("前面你说的数据量是多少？")
    assert refers_to_earlier_talk("你刚说的那个方案怎么做的？")
    assert not refers_to_earlier_talk("上一次的项目里，你怎么做的分库分表？")
    assert not refers_to_earlier_talk("讲讲你做过的一次性能优化。")


async def test_skipping_a_follow_up_moves_on_without_judging_its_main_again(db, model):
    """Skipping a follow-up skips its main question too: no second follow-up on it, and the reply
    says the question is changed."""
    await _turn(db, "你好")
    await _turn(db, "我叫张三。")
    model.followup = {"followup": True, "question": "样本量是怎么算出来的？",
                      "quotes": ["样本量按每组五千人来定"]}
    assert await _turn(db, ANSWER) == "样本量是怎么算出来的？"
    calls_before = list(model.calls)
    reply = await _turn(db, "下一题")
    assert reply.startswith(flow.SKIP_TEXT)
    assert model.calls[len(calls_before):].count("followup") == 0
    state = await _coverage(db)
    assert "q01" in state["closed_mains"]


async def test_a_bank_question_that_points_back_is_never_offered(db, model):
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


async def test_repeat_request_says_the_last_words_exactly(db, model, monkeypatch):
    """"没听清" repeats what was said last, word for word, and does not re-word it."""
    async def reword(skill_id, payload, caller):
        if payload["task"] == "phrase":
            return {"question": "这次换了说法，你做过哪件事？"}
        return {"question": payload.get("question", "")}

    await _turn(db, "你好")
    monkeypatch.setattr(flow, "_model_json", reword)
    first = await _turn(db, "我叫张三。")
    monkeypatch.setattr(flow, "_model_json", model)
    again = await _turn(db, "没听清，能再说一遍吗")
    assert again == first.split("\n")[-1]
