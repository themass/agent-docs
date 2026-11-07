"""An interview reply reaches the candidate with one question (E-02).

A reply with two question marks is asked once more to keep one, and only the corrected reply is
shown and stored. The first reply is never shown to the candidate. Chats that are not an interview
are streamed as they always were."""

from __future__ import annotations

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.interview import InterviewQuestion, MockSession
from jc.models.profile import Profile
from jc.models.user import User
from jc.schemas.agent import AgentUiContext
from jc.services import agent_service
from jc.services.interview_reply import REWRITE_MESSAGE, needs_one_question, question_count

TWO = "你刚说新手任务提高了转化。那这个提高是实验组对照组比出来的吗？对照组同期是什么水平？"
ONE = "你刚说新手任务把首单转化从 4.1% 提到 5.3%。这个提升你是拿什么判断它来自新手任务的？"
FIXED = "你刚说新手任务把首单转化从 4.1% 提到 5.3%。这个提升有没有排除其它因素？"


class ScriptedClient:
    """Answers each call with the next scripted reply, and records what it was asked."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.asked: list[str] = []

    async def stream_message(self, thread_id, message, metadata=None):
        self.asked.append(message)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            yield {"type": "error", "message": "boom"}
            return
        yield {"type": "token", "content": reply}
        yield {"type": "done"}


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/one_question.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user", payload={}, version=1))
        db.add(InterviewQuestion(id="q1", profile_id="p1", stem="讲一个你拆分数据的经历",
                                 question_type="behavioral"))
        db.add(MockSession(id="ms1", profile_id="p1", user_id="u1", mode="target",
                           question_ids=["q1"], bank_draw_count=0, generated_count=0,
                           status="active", started_at=_now(), style="standard", level="mid",
                           coverage={"asked": [{"question_id": "q1", "kind": "main",
                                                "parent_question_id": None}]}))
        db.add(AgentSession(id="as1", user_id="u1", profile_id="p1", role_id="coach-mock",
                            deerflow_thread_id="thread"))
        await db.commit()
    yield makers
    await engine.dispose()


def _now():
    from datetime import UTC, datetime
    return datetime.now(UTC)


async def _turn(maker, monkeypatch, client, *, mock_session_id: str | None = "ms1"):
    from jc.services import agent_service as module

    monkeypatch.setattr(module, "get_deerflow_client", lambda db=None: client)
    ui = AgentUiContext(mock_session_id=mock_session_id) if mock_session_id else None
    async with maker() as db:
        events = [
            event async for event in agent_service.AgentService(db).stream_message(
                "as1",
                actor=UserActor(user_id="u1", session_id="s"),
                content="我把结算接口拆成了两张表。",
                ui_context=ui,
            )
        ]
    return [e for e in events if e.get("type") == "token"]


async def _stored_replies(maker) -> list[str]:
    async with maker() as db:
        rows = (await db.execute(
            select(AgentMessage).where(AgentMessage.role == "assistant")
        )).scalars().all()
    return [row.content for row in rows if row.content]


def test_counting_question_marks_in_both_scripts():
    assert question_count(TWO) == 2 and question_count(ONE) == 1
    assert needs_one_question(TWO) and not needs_one_question(ONE)
    assert question_count("你怎么看？这个呢?") == 2


@pytest.mark.asyncio
async def test_a_reply_with_one_question_goes_out_once_and_unchanged(maker, monkeypatch):
    client = ScriptedClient(ONE)
    tokens = await _turn(maker, monkeypatch, client)
    assert "".join(t["content"] for t in tokens) == ONE
    assert len(client.asked) == 1


@pytest.mark.asyncio
async def test_a_reply_with_two_questions_is_corrected_and_only_the_correction_is_shown(
    maker, monkeypatch
):
    client = ScriptedClient(TWO, FIXED)
    tokens = await _turn(maker, monkeypatch, client)
    shown = "".join(t["content"] for t in tokens)
    assert shown == FIXED, "the candidate must never see the two-question reply"
    assert client.asked[1] == REWRITE_MESSAGE
    assert question_count(shown) == 1


@pytest.mark.asyncio
async def test_the_stored_reply_is_the_corrected_one(maker, monkeypatch):
    client = ScriptedClient(TWO, FIXED)
    await _turn(maker, monkeypatch, client)
    stored = await _stored_replies(maker)
    assert FIXED in stored and TWO not in stored


@pytest.mark.asyncio
async def test_when_the_correction_fails_the_first_reply_is_shown_as_it_was(maker, monkeypatch):
    client = ScriptedClient(TWO, RuntimeError("the model is down"))
    tokens = await _turn(maker, monkeypatch, client)
    assert "".join(t["content"] for t in tokens) == TWO
    assert len(client.asked) == 2


@pytest.mark.asyncio
async def test_a_correction_that_is_an_error_event_falls_back_to_the_first_reply(
    maker, monkeypatch
):
    client = ScriptedClient(TWO, Exception("provider error"))
    tokens = await _turn(maker, monkeypatch, client)
    assert "".join(t["content"] for t in tokens) == TWO


@pytest.mark.asyncio
async def test_a_chat_that_is_not_an_interview_is_never_corrected(maker, monkeypatch):
    client = ScriptedClient(TWO)
    tokens = await _turn(maker, monkeypatch, client, mock_session_id=None)
    assert "".join(t["content"] for t in tokens) == TWO
    assert len(client.asked) == 1


async def _markers(maker) -> list[dict]:
    from jc.models.agent_trace import AgentTrace

    async with maker() as db:
        rows = (await db.execute(
            select(AgentTrace).where(AgentTrace.event_type == "interview_reply_corrected")
        )).scalars().all()
    return [{"outcome": r.payload["outcome"], "mock": r.mock_session_id} for r in rows]


@pytest.mark.asyncio
async def test_a_correction_leaves_a_marker_saying_it_worked(maker, monkeypatch):
    await _turn(maker, monkeypatch, ScriptedClient(TWO, FIXED))
    assert await _markers(maker) == [{"outcome": "corrected", "mock": "ms1"}]


@pytest.mark.asyncio
async def test_a_failed_correction_leaves_a_kept_first_marker(maker, monkeypatch):
    await _turn(maker, monkeypatch, ScriptedClient(TWO, RuntimeError("down")))
    assert await _markers(maker) == [{"outcome": "kept_first", "mock": "ms1"}]


@pytest.mark.asyncio
async def test_a_reply_that_needed_no_correction_leaves_no_marker(maker, monkeypatch):
    await _turn(maker, monkeypatch, ScriptedClient(ONE))
    assert await _markers(maker) == []


def test_corrections_are_counted_from_the_ledger_rows():
    from types import SimpleNamespace

    from jc.coach.recording import corrections_from_trace

    rows = [
        SimpleNamespace(event_type="interview_reply_corrected", payload={"outcome": "corrected"}),
        SimpleNamespace(event_type="interview_reply_corrected", payload={"outcome": "kept_first"}),
        SimpleNamespace(event_type="assistant_message", payload={"text": "x"}),
        SimpleNamespace(event_type="interview_reply_corrected", payload={"outcome": "weird"}),
    ]
    assert corrections_from_trace(rows) == {"corrected": 1, "kept_first": 1}
