"""LLM transport primitives: message mapping, pricing, multimodal input.

The pieces here have no opinion about routing, retries, audit or product
semantics — they convert shapes and compute numbers. That is exactly why they
were worth extracting: every agent service builds a model call, and every one of
them would otherwise hand-assemble the same OpenAI wire format and the same
token-price arithmetic.

What is deliberately NOT here yet:

- **Routing** (`routing.yaml` scenarios, failover chains, credentials). The shape
  of a chain is a deployment's policy; a service that only needs one model should
  not have to adopt a scenario vocabulary to get one.
- **Audit sinks.** Where a call record goes is per-service storage.

Those stay in the service that owns them until a second service actually needs
the same shell. Auto (the current caller) is the reference implementation.
"""

from __future__ import annotations

from .message_mapping import content_text, role_for, to_litellm_messages, tool_calls_from
from .pricing import ModelPrice, parse_pricing, price_for

__all__ = [
    "ModelPrice",
    "content_text",
    "parse_pricing",
    "price_for",
    "role_for",
    "to_litellm_messages",
    "tool_calls_from",
]
