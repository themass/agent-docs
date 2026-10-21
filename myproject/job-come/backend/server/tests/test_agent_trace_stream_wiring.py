"""AgentService.stream_message writes a full jc_agent_trace ledger alongside
the existing jc_agent_message UI projection.

Covers the three things that were easy to get wrong in the wiring:
  * `system_prompt` lands at seq 0, exactly once per session, even across
    multiple turns.
  * `user_message` carries the literal text sent to the model (post profile
    digest / locale wrapping), not the raw textbox value.
  * `reasoning` / `tool_call` / `tool_result` rows carry the untruncated
    `full_content` / `full_result` text, not the UI-sized `content` / `result`
    the SSE stream itself uses.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jc.db.base import Base
from jc.models import *  # noqa: F403
from jc.models.agent import AgentSession
from jc.models.user import User
from jc.services import agent_service as agent_service_module
from jc.services.agent_service import AgentService
from jc.stores.agent_trace_store import AgentTraceStore


class _FakeSessionClient:
    """Stands in for `DeerFlowHarnessSessionClient`: replays a fixed event script."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events

    async def stream_message(
        self, thread_id: str, message: str, **kwargs: Any
    ) -> AsyncIterator[dict]:
        for event in self._events:
            yield event


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(User(id="usr_1", email="u@example.test", password_hash="x"))
        session.add(AgentSession(id="agsn_1", user_id="usr_1", deerflow_thread_id="thread_1"))
        await session.commit()
        yield session
    await engine.dispose()


def _actor() -> UserActor:
    return UserActor(user_id="usr_1", session_id="sess_1")


LONG_REASONING = "思考过程" * 2000  # well past the 4000-char UI cut


def _script() -> list[dict[str, Any]]:
    return [
        {"type": "system_prompt_rendered", "content": "你是舟卡，一名简历优化助手。"},
        {"type": "skill", "name": "resume-coach"},
        {
            "type": "thinking",
            "content": LONG_REASONING[:4000],
            "full_content": LONG_REASONING,
        },
        {"type": "tool_start", "name": "jc_read_profile", "args": {"section": "experience"}},
        {
            "type": "tool_result",
            "name": "jc_read_profile",
            "result": ("x" * 2000),
            "full_result": ("x" * 2000) + "-this-tail-is-only-in-full-result",
        },
        {"type": "token", "content": "已经帮你优化好了。"},
        {"type": "usage", "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        {"type": "done"},
    ]


@pytest.mark.asyncio
async def test_system_prompt_lands_at_seq_zero_once(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(_script())
    )
    service = AgentService(db)
    events = [
        e async for e in service.stream_message("agsn_1", actor=_actor(), content="帮我优化简历")
    ]

    trace = AgentTraceStore(db)
    rows = await trace.list_for_session("agsn_1")
    assert rows[0].event_type == "system_prompt"
    assert rows[0].seq == 0
    assert rows[0].payload["text"] == "你是舟卡，一名简历优化助手。"

    # The internal `system_prompt_rendered` event must never reach the SSE client.
    assert all(e.get("type") != "system_prompt_rendered" for e in events)


@pytest.mark.asyncio
async def test_system_prompt_is_not_duplicated_on_a_second_turn(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(_script())
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="第一轮"):
        pass
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="第二轮"):
        pass

    trace = AgentTraceStore(db)
    rows = await trace.list_for_session("agsn_1")
    system_prompt_rows = [r for r in rows if r.event_type == "system_prompt"]
    assert len(system_prompt_rows) == 1
    assert system_prompt_rows[0].seq == 0


@pytest.mark.asyncio
async def test_user_message_carries_the_literal_model_input(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(_script())
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="帮我优化简历"):
        pass

    trace = AgentTraceStore(db)
    rows = await trace.list_for_session("agsn_1")
    user_rows = [r for r in rows if r.event_type == "user_message"]
    assert len(user_rows) == 1
    # Not just the raw textbox string: the reply-locale instruction this turn
    # actually prepends before sending to the model must be present too.
    assert "帮我优化简历" in user_rows[0].payload["text"]


@pytest.mark.asyncio
async def test_the_user_message_row_is_the_users_turn_not_standing_policy(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reply-language rule used to be prepended to every turn unconditionally.

    It is system content now (`jc.agent.standing_instructions`, rendered by
    `JCProductRulesMiddleware`), so a `user_message` row that still carries it
    means the duplicate prepend came back -- which is both a per-turn token cost
    and the thing that made this ledger unreadable: finding what someone asked
    meant hunting for it behind a wall of instructions.
    """
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(_script())
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="帮我优化简历"):
        pass

    rows = await AgentTraceStore(db).list_for_session("agsn_1")
    text = next(r for r in rows if r.event_type == "user_message").payload["text"]

    assert "帮我优化简历" in text
    assert "你必须全程使用简体中文回复" not in text
    assert "不要自我介绍" not in text
    assert "ask_clarification" not in text


@pytest.mark.asyncio
async def test_reasoning_and_tool_rows_keep_the_untruncated_text(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(_script())
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="帮我优化简历"):
        pass

    trace = AgentTraceStore(db)
    rows = await trace.list_for_session("agsn_1")

    reasoning_rows = [r for r in rows if r.event_type == "reasoning"]
    assert len(reasoning_rows) == 1
    assert reasoning_rows[0].payload["text"] == LONG_REASONING
    assert len(reasoning_rows[0].payload["text"]) > 4000

    tool_call_rows = [r for r in rows if r.event_type == "tool_call"]
    assert tool_call_rows[0].payload == {
        "name": "jc_read_profile",
        "arguments": {"section": "experience"},
    }

    tool_result_rows = [r for r in rows if r.event_type == "tool_result"]
    assert tool_result_rows[0].payload["result"].endswith("-this-tail-is-only-in-full-result")


@pytest.mark.asyncio
async def test_assistant_message_is_the_final_row(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(_script())
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="帮我优化简历"):
        pass

    trace = AgentTraceStore(db)
    rows = await trace.list_for_session("agsn_1")
    assert rows[-1].event_type == "assistant_message"
    assert rows[-1].payload["text"] == "已经帮你优化好了。"


@pytest.mark.asyncio
async def test_a_run_with_no_system_prompt_event_still_writes_user_message(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defensive path: if the embedded client never exposes a rendered prompt
    (e.g. an error before the first raw event), the user's own turn must not
    be silently dropped."""
    script = [e for e in _script() if e.get("type") != "system_prompt_rendered"]
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(script)
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="帮我优化简历"):
        pass

    trace = AgentTraceStore(db)
    rows = await trace.list_for_session("agsn_1")
    user_rows = [r for r in rows if r.event_type == "user_message"]
    assert len(user_rows) == 1
    system_prompt_rows = [r for r in rows if r.event_type == "system_prompt"]
    assert len(system_prompt_rows) == 0


@pytest.mark.asyncio
async def test_failed_run_stores_traceback_in_trace_but_not_in_sse(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed run's diagnosis must survive in the ledger, not only in stdout.

    This is the regression for the failure mode that made "agent 从来没成功过"
    undiagnosable: the harness turned an exception into `{"type": "error",
    "message": str(exc)}`, the frontend sanitizer replaced that with generic
    Chinese copy, and the traceback existed only in the server process's
    stdout. Nothing in the database said where the run died.
    """
    script = [
        {"type": "system_prompt_rendered", "content": "系统提示"},
        {"type": "tool_start", "name": "jc_profile_get", "args": {}},
        {
            "type": "error",
            "message": "litellm.APIError: provider blew up",
            "diagnostics": {
                "exception_type": "litellm.exceptions.APIError",
                "stage": "stream",
                "open_tools": ["jc_profile_get"],
                "traceback": "Traceback (most recent call last):\n  ...\nAPIError",
            },
        },
        {"type": "done"},
    ]
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(script)
    )
    service = AgentService(db)
    events = [
        e async for e in service.stream_message("agsn_1", actor=_actor(), content="帮我改简历")
    ]

    rows = await AgentTraceStore(db).list_for_session("agsn_1")
    error_rows = [r for r in rows if r.event_type == "error"]
    assert len(error_rows) == 1
    payload = error_rows[0].payload
    assert payload["exception_type"] == "litellm.exceptions.APIError"
    assert payload["stage"] == "stream"
    assert payload["open_tools"] == ["jc_profile_get"]
    assert "Traceback" in payload["traceback"]
    # The user-facing text is still carried, because the frontend sanitizer
    # classifies on it (rate limit vs timeout vs outage).
    assert "provider blew up" in payload["message"]

    # ...and the traceback must not be shipped to the browser.
    sse_errors = [e for e in events if e.get("type") == "error"]
    assert len(sse_errors) == 1
    assert "diagnostics" not in sse_errors[0]
    assert "traceback" not in sse_errors[0]


@pytest.mark.asyncio
async def test_error_without_diagnostics_still_writes_a_trace_row(
    db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rows written before diagnostics existed, and any future producer that
    still queues a bare exception, must not lose the error row entirely."""
    script = [
        {"type": "error", "message": "cancelled"},
        {"type": "done"},
    ]
    monkeypatch.setattr(
        agent_service_module, "get_deerflow_client", lambda db=None: _FakeSessionClient(script)
    )
    service = AgentService(db)
    async for _ in service.stream_message("agsn_1", actor=_actor(), content="停"):
        pass

    rows = await AgentTraceStore(db).list_for_session("agsn_1")
    error_rows = [r for r in rows if r.event_type == "error"]
    assert len(error_rows) == 1
    assert error_rows[0].payload == {"message": "cancelled"}


@pytest.mark.asyncio
async def test_confirmation_is_committed_before_publishing_and_disconnect(db, monkeypatch):
    from sqlalchemy import select

    from jc.models.agent_message import AgentMessage

    events = [
        {"type": "system_prompt_rendered", "content": "system"},
        {"type": "confirm", "confirm_id": "cfm_test", "patch": {"summary": "changed"}},
        {"type": "token", "content": "请确认"},
    ]
    monkeypatch.setattr(agent_service_module, "get_deerflow_client",
                        lambda db=None: _FakeSessionClient(events))
    stream = AgentService(db).stream_message("agsn_1", actor=_actor(), content="修改")
    event = await anext(stream)
    assert event["type"] == "confirm"
    assert not db.in_transaction(), "Visible confirm still holds an uncommitted transaction"
    # A disconnected HTTP client closes at this exact yield. Its cleanup rollback
    # must not remove the confirmation the user has already seen.
    await stream.aclose()
    await db.rollback()
    result = await db.execute(select(AgentMessage).where(AgentMessage.event_type == "confirm"))
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_done_means_assistant_reply_is_already_durable(db, monkeypatch):
    from sqlalchemy import select

    from jc.models.agent_message import AgentMessage
    monkeypatch.setattr(agent_service_module, "get_deerflow_client",
                        lambda db=None: _FakeSessionClient(_script()))
    stream = AgentService(db).stream_message("agsn_1", actor=_actor(), content="修改")
    seen_done = False
    async for event in stream:
        if event["type"] == "done":
            seen_done = True
            assert not db.in_transaction()
            # Simulate cleanup immediately after the terminal event.
            await db.rollback()
            rows = (await db.execute(select(AgentMessage).where(
                AgentMessage.role == "assistant", AgentMessage.event_type == "message",
            ))).scalars().all()
            assert len(rows) == 1 and rows[0].content == "已经帮你优化好了。"
    assert seen_done


@pytest.mark.asyncio
async def test_full_audit_payload_not_duplicated_to_ui_message_or_sse(db, monkeypatch):
    from sqlalchemy import select

    from jc.models.agent_message import AgentMessage
    monkeypatch.setattr(agent_service_module, "get_deerflow_client",
                        lambda db=None: _FakeSessionClient(_script()))
    events = [e async for e in AgentService(db).stream_message(
        "agsn_1", actor=_actor(), content="修改",
    )]
    assert all("full_content" not in e and "full_result" not in e for e in events)
    rows = (await db.execute(select(AgentMessage))).scalars().all()
    assert all('"full_content"' not in (r.payload_json or "") and
               '"full_result"' not in (r.payload_json or "") for r in rows)
    traces = await AgentTraceStore(db).list_for_session("agsn_1")
    assert next(r for r in traces if r.event_type == "reasoning").payload["text"] == LONG_REASONING


@pytest.mark.asyncio
async def test_failed_tool_turn_never_becomes_processing_complete_on_replay(db, monkeypatch):
    from sqlalchemy import select

    from jc.models.agent_message import AgentMessage
    script = [
        {"type": "system_prompt_rendered", "content": "system"},
        {"type": "tool_start", "name": "jc_profile_patch", "args": {}},
        {"type": "error", "message": "本次处理失败"},
        {"type": "done"},
    ]
    monkeypatch.setattr(agent_service_module, "get_deerflow_client",
                        lambda db=None: _FakeSessionClient(script))
    events = [e async for e in AgentService(db).stream_message(
        "agsn_1", actor=_actor(), content="修改",
    )]
    assert events[-1]["type"] == "done"
    rows = (await db.execute(select(AgentMessage).where(
        AgentMessage.role == "assistant", AgentMessage.event_type == "message",
    ))).scalars().all()
    assert not rows


@pytest.mark.asyncio
async def test_resume_turn_uses_live_bounded_index_not_whole_profile(db, monkeypatch):
    from types import SimpleNamespace

    from jc.models.profile import Profile
    from jc.schemas.profile_payload import ProfilePayload

    payload = ProfilePayload.model_validate({"contact": {"name": "用户"}, "experiences": [{
        "id": "e1", "company": "甲", "title": "开发", "start_date": "2020",
        "highlights": ["长篇事实" * 1000] * 10,
    }]})
    db.add(Profile(id="prof_ctx", user_id="usr_1", owner_kind="user", payload=payload.model_dump(mode="json")))
    session = await db.get(AgentSession, "agsn_1")
    session.profile_id = "prof_ctx"
    await db.commit()
    messages = []

    class RecordingClient(_FakeSessionClient):
        async def stream_message(self, thread_id, message, **kwargs):
            messages.append(message)
            async for event in super().stream_message(thread_id, message, **kwargs):
                yield event

    monkeypatch.setattr(agent_service_module, "get_deerflow_client", lambda db=None: RecordingClient(_script()))
    service = AgentService(db)
    from unittest.mock import AsyncMock
    service._profiles.get = AsyncMock(return_value=SimpleNamespace(payload=payload, version=7))
    for _ in range(2):
        async for _event in service.stream_message("agsn_1", actor=_actor(), content="看看我的简历"):
            pass
    assert len(messages) == 2
    for message in messages:
        assert "长篇事实" not in message
        assert "profile_version=7" in message and '"count": 1' in message
        assert len(message) < 2000
