"""Rebuild LLM chat history from persisted agent messages."""

from __future__ import annotations

from typing import Any

from jobcome.models.agent_message import AgentMessage


def history_to_chat_messages(rows: list[AgentMessage]) -> list[dict[str, Any]]:
    """Convert stored turns into OpenAI-style messages (user/assistant text only)."""
    messages: list[dict[str, Any]] = []
    for row in rows:
        if row.event_type != "message":
            continue
        if row.role not in {"user", "assistant"}:
            continue
        content = (row.content or "").strip()
        if not content:
            continue
        messages.append({"role": row.role, "content": content})
    return messages
