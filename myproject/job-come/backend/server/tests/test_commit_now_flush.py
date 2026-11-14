"""_COMMIT_NOW_EVENT_TYPES: confirm/error land before yield; soft events may batch."""

from __future__ import annotations

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentkit.web.auth import UserActor

from jc.agent.roles import default_role
from jc.db.base import Base
from jc.models.agent import AgentSession
from jc.models.agent_trace import AgentTrace
from jc.models.user import User
from jc.services import agent_service
from jc.services.agent_service import _COMMIT_NOW_EVENT_TYPES


@pytest.fixture
async def maker(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/commit_now.sqlite")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(User(id="u1", email="u1@example.test", password_hash="test"))
        await db.flush()
        db.add(
            AgentSession(
                id="as1",
                user_id="u1",
                profile_id="p1",
                role_id=default_role().id,
                deerflow_thread_id="thr_1",
                trace_id="tr_1",
            )
        )
        await db.commit()
    yield sessions
    await engine.dispose()


class _ScriptedClient:
    def __init__(self, events: list[dict]):
        self.events = events

    async def stream_message(self, thread_id, message, metadata=None):
        for ev in self.events:
            yield ev


async def _count_traces(maker) -> int:
    async with maker() as db:
        return len(
            list(
                (
                    await db.execute(select(AgentTrace).where(AgentTrace.session_id == "as1"))
                ).scalars()
            )
        )


async def _event_types(maker) -> list[str]:
    async with maker() as db:
        rows = list(
            (
                await db.execute(
                    select(AgentTrace)
                    .where(AgentTrace.session_id == "as1")
                    .order_by(AgentTrace.seq)
                )
            ).scalars()
        )
    return [r.event_type for r in rows]


@pytest.mark.asyncio
async def test_confirm_is_committed_before_it_is_yielded(maker, monkeypatch):
    assert "confirm" in _COMMIT_NOW_EVENT_TYPES
    client = _ScriptedClient(
        [
            {"type": "system_prompt_rendered", "content": "sys"},
            {
                "type": "confirm",
                "confirm_id": "c1",
                "name": "jc_profile_patch",
                "patch": {"contact": {"name": "x"}},
            },
            {"type": "token", "content": "ok"},
            {"type": "done"},
        ]
    )
    monkeypatch.setattr(agent_service, "get_deerflow_client", lambda db=None: client)

    seen_confirm = False
    async with maker() as db:
        stream = agent_service.AgentService(db).stream_message(
            "as1",
            actor=UserActor(user_id="u1", session_id="s"),
            content="请确认",
        )
        async for ev in stream:
            if ev.get("type") == "confirm":
                seen_confirm = True
                # Must already be durable for a concurrent reader.
                async with maker() as reader:
                    types = [
                        r.event_type
                        for r in (
                            await reader.execute(
                                select(AgentTrace).where(AgentTrace.session_id == "as1")
                            )
                        ).scalars()
                    ]
                assert "confirm" in types or "tool_call" in types or any(
                    "confirm" in t for t in types
                ), types
    assert seen_confirm


@pytest.mark.asyncio
async def test_thinking_and_tool_start_may_batch_without_immediate_solo_commit(
    maker, monkeypatch
):
    """Soft events accumulate; a mid-stream reader may not see them until a commit-now or end."""
    client = _ScriptedClient(
        [
            {"type": "system_prompt_rendered", "content": "sys"},
            {"type": "thinking", "content": "…", "full_content": "thinking hard"},
            {"type": "tool_start", "name": "jc_profile_get", "args": {"section": "contact"}},
            {"type": "token", "content": "hi"},
            {"type": "done"},
        ]
    )
    monkeypatch.setattr(agent_service, "get_deerflow_client", lambda db=None: client)

    mid_counts: list[int] = []
    async with maker() as db:
        stream = agent_service.AgentService(db).stream_message(
            "as1",
            actor=UserActor(user_id="u1", session_id="s"),
            content="查一下",
        )
        async for ev in stream:
            if ev.get("type") in {"thinking", "tool_start"}:
                mid_counts.append(await _count_traces(maker))
    # After the turn, soft events are present.
    final_types = await _event_types(maker)
    assert "reasoning" in final_types or "tool_call" in final_types, final_types
    # At least one mid-stream observation saw fewer rows than the final ledger
    # (batching deferred the write) — if every soft event committed immediately,
    # mid counts would already equal the final soft-event count.
    final_n = await _count_traces(maker)
    assert mid_counts, "expected to observe soft events"
    assert min(mid_counts) < final_n


@pytest.mark.asyncio
async def test_exception_mid_turn_still_persists_accumulated_rows(maker, monkeypatch):
    """If the stream dies mid-turn, already-batched rows must not vanish.

    This began as an `xfail(strict=True)` witness for a real bug: the turn body
    had no `finally`, so an exception between a `thinking`/`tool_start` event and
    the end of the turn discarded every row already built. The same missing
    `finally` also left `agent_turns_in_flight` raised forever, which is precisely
    the alert that gauge exists to give.

    Now a regression test: if the flush ever moves back inside the success path,
    this fails again.
    """

    class _BoomClient:
        async def stream_message(self, thread_id, message, metadata=None):
            yield {"type": "system_prompt_rendered", "content": "sys"}
            yield {"type": "thinking", "content": "…", "full_content": "partial"}
            yield {"type": "tool_start", "name": "jc_profile_get", "args": {}}
            raise RuntimeError("boom mid-turn")

    monkeypatch.setattr(agent_service, "get_deerflow_client", lambda db=None: _BoomClient())

    with pytest.raises(RuntimeError, match="boom"):
        async with maker() as db:
            stream = agent_service.AgentService(db).stream_message(
                "as1",
                actor=UserActor(user_id="u1", session_id="s"),
                content="会炸",
            )
            async for _ in stream:
                pass

    types = await _event_types(maker)
    # Soft rows that were only sitting in pending_rows must survive.
    # system_prompt/user_message alone are not enough — those commit before the
    # model stream. The boom is after thinking + tool_start entered pending.
    assert "reasoning" in types or "tool_call" in types, (
        f"pending soft events were lost on mid-turn failure: {types!r}"
    )
