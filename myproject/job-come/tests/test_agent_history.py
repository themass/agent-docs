"""Agent history rebuild tests."""

from __future__ import annotations

from datetime import UTC, datetime

from jobcome.agent.history import history_to_chat_messages
from jobcome.models.agent_message import AgentMessage


def test_history_to_chat_messages_skips_events() -> None:
    rows = [
        AgentMessage(
            id="a1",
            session_id="s1",
            role="user",
            event_type="message",
            content="hello",
            payload_json=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        AgentMessage(
            id="a2",
            session_id="s1",
            role="assistant",
            event_type="tool_start",
            content=None,
            payload_json='{"name":"jobcome_profile_get"}',
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        AgentMessage(
            id="a3",
            session_id="s1",
            role="assistant",
            event_type="message",
            content="hi back",
            payload_json=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]
    msgs = history_to_chat_messages(rows)
    assert msgs == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi back"},
    ]
