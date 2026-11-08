"""The interviewer's opening is written by the server, and a silent model run is answered by the
watchdog (see jc/services/mock_opening.py)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import jc.models  # noqa: F401
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.interview import MockSession
from jc.models.job import Job
from jc.models.profile import Profile
from jc.models.user import User
from jc.schemas.agent import AgentUiContext
from jc.services import agent_service
from jc.services.mock_opening import HOLDING_TEXT, opening_text

ANSWER = "我做过三年用户增长，负责注册到首单的转化。"
QUESTION = "你刚说注册到首单的转化，那个转化率是怎么算的？"


class ScriptedClient:
    def __init__(self, *replies, delay: float = 0.0):
        self.replies = list(replies)
        self.delay = delay
        self.asked: list[str] = []

    async def stream_message(self, thread_id, message, metadata=None):
        self.asked.append(message)
        if self.delay:
            await asyncio.sleep(self.delay)
        yield {"type": "token", "content": self.replies.pop(0)}
        yield {"type": "done"}


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/opening.sqlite")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    makers = async_sessionmaker(engine, expire_on_commit=False)
    async with makers() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="x", role="user"))
        await db.flush()
        db.add(Profile(id="p1", user_id="u1", owner_kind="user", payload={}, version=1))
        db.add(Job(id="j1", profile_id="p1", company="示例科技", title="用户增长运营经理",
                   raw_text="JD", requirements={}))
        db.add(MockSession(id="ms1", profile_id="p1", user_id="u1", mode="target",
                           job_id="j1", question_ids=[], bank_draw_count=0, generated_count=0,
                           status="active", started_at=datetime.now(UTC), style="standard",
                           level="mid", coverage={"asked": []}))
        db.add(AgentSession(id="as1", user_id="u1", profile_id="p1", job_id="j1",
                            role_id="coach-mock", deerflow_thread_id="thread"))
        await db.commit()
    yield makers
    await engine.dispose()


async def _turn(maker, monkeypatch, client, content):
    monkeypatch.setattr(agent_service, "get_deerflow_client", lambda db=None: client)
    async with maker() as db:
        events = [
            event async for event in agent_service.AgentService(db).stream_message(
                "as1", actor=UserActor(user_id="u1", session_id="s"), content=content,
                ui_context=AgentUiContext(mock_session_id="ms1"),
            )
        ]
    return "".join(e["content"] for e in events if e.get("type") == "token")


async def _state(maker) -> dict:
    async with maker() as db:
        return dict((await db.execute(select(MockSession))).scalar_one().coverage or {})


def test_the_opening_names_the_company_and_role_and_asks_for_a_self_introduction():
    text = opening_text("示例科技", "用户增长运营经理")
    assert "示例科技用户增长运营经理" in text
    assert "自我介绍" in text
    assert "?" not in text and "？" not in text


@pytest.mark.asyncio
async def test_the_first_message_gets_the_opening_without_the_model(maker, monkeypatch):
    client = ScriptedClient()
    shown = await _turn(maker, monkeypatch, client, "你好，我准备好了。")
    assert shown == opening_text("示例科技", "用户增长运营经理")
    assert client.asked == [], "the model must not be called for the opening"
    state = await _state(maker)
    assert state["opening_sent"] is True and state["opening_text"] == shown


@pytest.mark.asyncio
async def test_the_model_is_told_the_opening_once(maker, monkeypatch):
    await _turn(maker, monkeypatch, ScriptedClient(), "你好，我准备好了。")
    client = ScriptedClient(QUESTION)
    shown = await _turn(maker, monkeypatch, client, ANSWER)
    assert shown == QUESTION
    assert len(client.asked) == 1
    assert "面试开场白已由系统发出" in client.asked[0]
    assert ANSWER in client.asked[0]
    assert (await _state(maker))["opening_briefed"] is True

    client2 = ScriptedClient("好，那我们接着。")
    await _turn(maker, monkeypatch, client2, "好的。")
    assert "面试开场白已由系统发出" not in client2.asked[0]


@pytest.mark.asyncio
async def test_a_silent_model_run_is_answered_by_the_holding_line(maker, monkeypatch):
    await _turn(maker, monkeypatch, ScriptedClient(), "你好，我准备好了。")
    monkeypatch.setattr(agent_service, "WATCHDOG_SEC", 0.05)
    client = ScriptedClient(QUESTION, delay=1.0)
    shown = await _turn(maker, monkeypatch, client, ANSWER)
    assert shown == HOLDING_TEXT
    assert QUESTION not in shown
    async with maker() as db:
        stored = (await db.execute(
            select(AgentMessage).where(AgentMessage.role == "assistant")
        )).scalars().all()
    assert HOLDING_TEXT in [m.content for m in stored]
