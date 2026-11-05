"""The system records what the candidate says, onto the question on the table.

The interviewer used to be asked to save each answer with a tool, so one forgotten call left a
question "unanswered" in the report. The service now writes the answer before the model runs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.models.interview import AnswerAttempt, InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.services.mock_answer_recorder import record_mock_answer, records_mock_answer

MAIN = {"question_id": "q1", "kind": "main", "parent_question_id": None}
FOLLOW_UP = {"question_id": "q2", "kind": "followup", "parent_question_id": "q1"}


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/recorder.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        for profile_id in ("p1", "p2"):
            db.add(Profile(id=profile_id, user_id="u1", owner_kind="user",
                           payload={"experience": "结算接口拆表"}, version=1))
        db.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲一个你拆分数据的经历",
                                 question_type="behavioral"))
        db.add(InterviewQuestion(id="q2", profile_id="p1", stem="拆表时怎么保证数据一致",
                                 question_type="behavioral"))
        await db.commit()
    yield makers
    await engine.dispose()


async def _open_session(maker, asked: list[dict], *, status: str = "active") -> None:
    async with maker() as db:
        db.add(MockSession(
            id="ms1", profile_id="p1", user_id="u1", mode="target", question_ids=[],
            bank_draw_count=0, generated_count=0, status=status,
            started_at=datetime.now(UTC), style="standard", coverage={"asked": asked},
        ))
        await db.commit()


async def _record(maker, text: str, *, profile_id: str = "p1") -> str | None:
    async with maker() as db:
        return await record_mock_answer(
            db, profile_id=profile_id, mock_session_id="ms1", text=text
        )


async def _attempts(maker) -> list[AnswerAttempt]:
    async with maker() as db:
        return list((await db.execute(select(AnswerAttempt))).scalars().all())


@pytest.mark.asyncio
async def test_the_first_message_after_a_question_becomes_its_answer(maker):
    await _open_session(maker, [MAIN])
    attempt_id = await _record(maker, "我把结算接口拆成了两张表。")
    rows = await _attempts(maker)
    assert [row.id for row in rows] == [attempt_id]
    assert (rows[0].question_id, rows[0].mock_session_id) == ("q1", "ms1")
    assert rows[0].user_answer == "我把结算接口拆成了两张表。"
    async with maker() as db:
        assert (await db.get(InterviewQuestion, "q1")).attempt_count == 1


@pytest.mark.asyncio
async def test_more_messages_on_the_same_question_extend_one_answer(maker):
    await _open_session(maker, [MAIN])
    first = await _record(maker, "我把结算接口拆成了两张表。")
    second = await _record(maker, "耗时三周，上线后没有回滚。")
    assert first == second
    rows = await _attempts(maker)
    assert len(rows) == 1
    assert rows[0].user_answer == "我把结算接口拆成了两张表。\n耗时三周，上线后没有回滚。"
    async with maker() as db:
        assert (await db.get(InterviewQuestion, "q1")).attempt_count == 1


@pytest.mark.asyncio
async def test_a_follow_up_gets_its_own_answer(maker):
    await _open_session(maker, [MAIN, FOLLOW_UP])
    await _record(maker, "靠双写加对账任务保证一致。")
    rows = await _attempts(maker)
    assert [(row.question_id, row.user_answer) for row in rows] == [
        ("q2", "靠双写加对账任务保证一致。")
    ]


@pytest.mark.asyncio
async def test_nothing_is_recorded_when_no_question_has_been_asked(maker):
    # The greeting and the self-introduction come before the first question.
    await _open_session(maker, [])
    assert await _record(maker, "你好，我准备好了。") is None
    assert await _attempts(maker) == []


@pytest.mark.asyncio
async def test_nothing_is_recorded_after_a_skip(maker):
    await _open_session(maker, [{**MAIN, "skipped": True}])
    assert await _record(maker, "那我们继续吧。") is None
    assert await _attempts(maker) == []


@pytest.mark.asyncio
async def test_nothing_is_recorded_for_a_closed_session(maker):
    await _open_session(maker, [MAIN], status="completed")
    assert await _record(maker, "补充一句。") is None
    assert await _attempts(maker) == []


@pytest.mark.asyncio
async def test_a_blank_message_is_not_an_answer(maker):
    await _open_session(maker, [MAIN])
    assert await _record(maker, "   \n ") is None
    assert await _attempts(maker) == []


@pytest.mark.asyncio
async def test_a_session_of_another_profile_gets_no_answer(maker):
    await _open_session(maker, [MAIN])
    with pytest.raises(PermissionError):
        await _record(maker, "不属于这个档案。", profile_id="p2")
    assert await _attempts(maker) == []


def test_only_the_practice_skill_of_the_interview_turn_records_answers():
    base = {"turn": "mock_session", "runtime_skill": "coach-mock",
            "default_skill": "coach-mock", "mock_session_id": "ms1"}
    assert records_mock_answer(**base) is True
    assert records_mock_answer(**{**base, "runtime_skill": "coach-archive"}) is False
    assert records_mock_answer(**{**base, "turn": "resume_profile"}) is False
    assert records_mock_answer(**{**base, "turn": None}) is False
    assert records_mock_answer(**{**base, "mock_session_id": None}) is False


async def _answered_then_follow_up_swapped(maker) -> None:
    """q1 asked and answered, q2 asked as a follow-up, then the candidate swaps q2 away."""
    from jc.authz.scope import RunScope
    from jc.services.mock_guard_service import swap

    await _open_session(maker, [MAIN, FOLLOW_UP])
    async with maker() as db:
        db.add(AnswerAttempt(id="a1", question_id="q1", profile_id="p1", mock_session_id="ms1",
                             user_answer="我把结算接口拆成了两张表。", coach_feedback={},
                             reference_answer=None))
        await db.commit()
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        result = await swap(scope, mock_session_id="ms1", question_id="q2")
    assert result["accepted"] is True


@pytest.mark.asyncio
async def test_nothing_is_recorded_after_a_swap(maker):
    # After a swap the last question asked is the earlier, already answered one. The candidate's
    # next words ("下一题") are not an addition to that answer.
    await _answered_then_follow_up_swapped(maker)
    assert await _record(maker, "下一题。") is None
    rows = await _attempts(maker)
    assert [row.user_answer for row in rows] == ["我把结算接口拆成了两张表。"]


@pytest.mark.asyncio
async def test_asking_a_new_question_after_a_swap_puts_the_table_back_in_use(maker):
    from jc.authz.scope import RunScope
    from jc.services.mock_guard_service import ask

    await _answered_then_follow_up_swapped(maker)
    async with maker() as db:
        db.add(InterviewQuestion(id="q3", profile_id="p1", stem="讲一次线上故障",
                                 question_type="behavioral"))
        await db.commit()
    async with maker() as db:
        scope = RunScope(db=db, user_id="u1", profile_id="p1", mock_session_id="ms1")
        asked = await ask(scope, mock_session_id="ms1", question_id="q3", kind="main")
    assert asked["accepted"] is True
    await _record(maker, "那次是缓存雪崩。")
    by_question = {row.question_id: row.user_answer for row in await _attempts(maker)}
    assert by_question["q3"] == "那次是缓存雪崩。"
    assert by_question["q1"] == "我把结算接口拆成了两张表。"


class _FakeClient:
    """A model client that answers with one token and records what it was sent."""

    def __init__(self) -> None:
        self.received: list[str] = []

    async def stream_message(self, thread_id, message, metadata=None):
        self.received.append(message)
        yield {"type": "token", "content": "好的。"}
        yield {"type": "done"}


async def _stream(maker, monkeypatch, text: str, *, mock_session_id: str | None = "ms1"):
    from agentkit.web.auth import UserActor

    from jc.models.agent import AgentSession
    from jc.schemas.agent import AgentUiContext
    from jc.services import agent_service

    client = _FakeClient()
    monkeypatch.setattr(agent_service, "get_deerflow_client", lambda db=None: client)
    async with maker() as db:
        if await db.get(AgentSession, "as1") is None:
            db.add(AgentSession(id="as1", user_id="u1", profile_id="p1", role_id="coach-mock",
                                deerflow_thread_id="thread"))
            await db.commit()
    async with maker() as db:
        ui_context = AgentUiContext(mock_session_id=mock_session_id) if mock_session_id else None
        events = [
            event async for event in agent_service.AgentService(db).stream_message(
                "as1", actor=UserActor(user_id="u1", session_id="s"), content=text,
                ui_context=ui_context)
        ]
    return client, events


@pytest.mark.asyncio
async def test_a_turn_records_the_users_words_and_the_model_gets_them_wrapped(
    maker, monkeypatch
):
    await _open_session(maker, [MAIN])
    client, _ = await _stream(maker, monkeypatch, "我把结算接口拆成了两张表。")
    rows = await _attempts(maker)
    # The record is what the candidate said, not the turn's task text wrapped around it.
    assert [(row.question_id, row.user_answer) for row in rows] == [
        ("q1", "我把结算接口拆成了两张表。")
    ]
    assert "【面试模拟任务】" in client.received[0]
    assert "我把结算接口拆成了两张表。" in client.received[0]


@pytest.mark.asyncio
async def test_a_turn_before_any_question_records_nothing_but_still_runs(maker, monkeypatch):
    await _open_session(maker, [])
    client, events = await _stream(maker, monkeypatch, "你好，我准备好了。")
    assert await _attempts(maker) == []
    assert len(client.received) == 1
    assert any(event.get("type") == "token" for event in events)


# --- messages that talk to the interview, not to the question -----------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "control",
    ["下一题", "下一题。", " 下一题！ ", "换一题", "换一道吧", "跳过", "跳过这题", "结束",
     "结束面试", "没听清", "没听清，能再说一遍吗", "再说一遍", "请重复一下问题", "能再问一次吗"],
)
async def test_a_message_that_only_steers_the_interview_is_not_an_answer(maker, control):
    await _open_session(maker, [MAIN])
    assert await _record(maker, control) is None
    assert await _attempts(maker) == []


@pytest.mark.asyncio
async def test_a_steering_message_does_not_touch_an_answer_already_given(maker):
    await _open_session(maker, [MAIN])
    await _record(maker, "我把结算接口拆成了两张表。")
    assert await _record(maker, "下一题") is None
    assert [row.user_answer for row in await _attempts(maker)] == ["我把结算接口拆成了两张表。"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [
        "我会跳过这个步骤直接上线，因为回滚成本很低。",
        "结束后我们做了复盘，发现下一题不用再改接口。",
        "当时用户说没听清，我又重复了一遍需求。",
        "换一种方案的话，我会先拆表再加缓存。",
    ],
)
async def test_a_real_answer_that_uses_the_same_words_is_still_recorded(maker, answer):
    await _open_session(maker, [MAIN])
    assert await _record(maker, answer) is not None
    assert [row.user_answer for row in await _attempts(maker)] == [answer]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "short", ["是的", "对", "不知道", "没有", "可以", "好的", "我没做过", "不会"]
)
async def test_a_very_short_real_answer_is_still_recorded(maker, short):
    await _open_session(maker, [MAIN])
    assert await _record(maker, short) is not None


def test_what_counts_as_steering_is_a_closed_list():
    from jc.services.mock_answer_recorder import is_steering_message

    assert is_steering_message("没听清，能再说一遍吗")
    assert not is_steering_message("没听清楚需求，所以我先和产品确认了一遍")
    assert not is_steering_message("")
    assert not is_steering_message("。。。")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "short_answer",
    ["我会跳过缓存", "结束后复盘了", "没听清楚就上线了", "换一种做法试过", "下一题再说"],
)
async def test_a_short_answer_with_a_steering_word_in_it_is_still_recorded(
    maker, short_answer
):
    # Short enough to pass any length check: only matching the whole message keeps these.
    await _open_session(maker, [MAIN])
    assert await _record(maker, short_answer) is not None
