"""Message mapping moved to `agentkit.llm.message_mapping`.

Converting LangChain messages into the OpenAI shape is a wire-format concern, not
a product one: any service that talks to a model through litellm needs exactly
these four functions, with exactly this tolerance for the shapes providers
actually return.

Kept as a re-export so the existing call sites (`jc.llm.chat_litellm`) and the
tests keep their import path; the implementation lives in one place only.
"""

from __future__ import annotations

from agentkit.llm.message_mapping import (
    content_text,
    role_for,
    to_litellm_messages,
    tool_calls_from,
)

__all__ = ["content_text", "role_for", "to_litellm_messages", "tool_calls_from"]
