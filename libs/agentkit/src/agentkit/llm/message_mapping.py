"""Message and content mapping between LangChain and litellm/OpenAI shapes.

Extracted from the adapter so the conversion rules are testable without a model
and without constructing a chat client. Both directions are deliberately
tolerant: providers return content as a string, a list of blocks, or a dict, and
an agent turn that drops a tool call because of an unexpected shape is much
harder to debug than one that renders slightly imperfect text.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

_ROLES: dict[type[BaseMessage], str] = {
    SystemMessage: "system",
    HumanMessage: "user",
    AIMessage: "assistant",
    ToolMessage: "tool",
}


def role_for(message: BaseMessage) -> str:
    """OpenAI wire role for a LangChain message."""
    for cls, role in _ROLES.items():
        if isinstance(message, cls):
            return role
    # ``type`` is LangChain's own discriminator; "ai"/"human" need translating.
    raw = getattr(message, "type", "user")
    return {"ai": "assistant", "human": "user"}.get(raw, raw)


def to_litellm_messages(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    """Convert LangChain messages to OpenAI-style dicts."""
    out: list[dict[str, Any]] = []
    for message in messages:
        role = role_for(message)
        entry: dict[str, Any] = {"role": role, "content": content_text(message.content)}
        if role == "tool":
            # Without tool_call_id the provider cannot match the result to the
            # call, and most gateways reject the whole request.
            entry["tool_call_id"] = getattr(message, "tool_call_id", None) or ""
        calls = (getattr(message, "additional_kwargs", None) or {}).get("tool_calls")
        if calls:
            entry["tool_calls"] = calls
            # An assistant turn that only makes tool calls has no text. Some
            # gateways reject "" but accept null.
            if not entry["content"]:
                entry["content"] = None
        out.append(entry)
    return out


def content_text(content: Any) -> str:
    """Flatten any provider content shape to plain text.

    Image blocks contribute nothing: this is used for assistant output and tool
    results, where a base64 payload in the text stream would be noise.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if content.get("type") in {"image_url", "image"}:
            return ""
        for key in ("text", "content"):
            value = content.get(key)
            if isinstance(value, str):
                return value
        return ""
    if isinstance(content, (list, tuple)):
        return "".join(content_text(part) for part in content)
    text = getattr(content, "text", None)
    return text if isinstance(text, str) else ""


def tool_calls_from(message: Any) -> list[dict[str, Any]]:
    """Normalize provider tool calls to the OpenAI dict shape."""
    raw = getattr(message, "tool_calls", None)
    if not raw:
        return []
    calls: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict):
            function = entry.get("function") or {}
            calls.append(
                {
                    "id": entry.get("id"),
                    "type": "function",
                    "function": {
                        "name": function.get("name"),
                        "arguments": function.get("arguments") or "",
                    },
                }
            )
            continue
        function = getattr(entry, "function", None)
        calls.append(
            {
                "id": getattr(entry, "id", None),
                "type": "function",
                "function": {
                    "name": getattr(function, "name", None),
                    "arguments": getattr(function, "arguments", None) or "",
                },
            }
        )
    return calls
