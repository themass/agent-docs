"""The extracted LLM primitives keep the semantics the service relied on.

These tests exist because the extraction must not change behaviour. Two
decisions are load-bearing and easy to "clean up" into bugs:

- an unpriced model reports None, never 0 — "we do not know" and "it was free"
  must not look the same in a cost report;
- a price configured under `openai/x` must match a response that echoes `x`,
  because the gateway does not return the litellm prefix.
"""

from __future__ import annotations

import pytest

from agentkit.llm import (
    ModelPrice,
    content_text,
    parse_pricing,
    price_for,
    role_for,
    to_litellm_messages,
    tool_calls_from,
)


def test_cost_is_micro_usd_from_a_per_million_quote():
    price = ModelPrice(prompt_usd_per_1m=2.5, completion_usd_per_1m=10.0)
    # 1000 * 2.5 + 500 * 10.0 = 7500 micro-USD, computed exactly in integers.
    assert price.micro_usd(prompt_tokens=1000, completion_tokens=500) == 7500


def test_no_token_counts_is_unknown_not_free():
    price = ModelPrice(prompt_usd_per_1m=1.0, completion_usd_per_1m=1.0)
    assert price.micro_usd(prompt_tokens=None, completion_tokens=None) is None


def test_a_price_matches_both_model_spellings():
    table = parse_pricing({"openai/x": {"prompt_usd_per_1m": 1, "completion_usd_per_1m": 2}})
    assert price_for(table, "openai/x") is not None
    assert price_for(table, "x") is not None


def test_an_unpriced_model_resolves_to_nothing():
    assert price_for({}, "nobody-knows-me") is None
    assert price_for({}, None) is None


def test_a_malformed_price_entry_is_skipped_not_fatal():
    table = parse_pricing({
        "good": {"prompt_usd_per_1m": 1, "completion_usd_per_1m": 2},
        "bad": {"prompt_usd_per_1m": "not a number"},
        "worse": "not a dict",
    })
    assert list(table) == ["good"]


def test_roles_translate_langchain_classes_to_wire_roles():
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    assert role_for(SystemMessage(content="s")) == "system"
    assert role_for(HumanMessage(content="h")) == "user"
    assert role_for(AIMessage(content="a")) == "assistant"
    assert role_for(ToolMessage(content="t", tool_call_id="c1")) == "tool"


def test_a_tool_result_carries_its_call_id():
    """Without it the provider cannot match result to call and rejects the request."""
    from langchain_core.messages import ToolMessage

    out = to_litellm_messages([ToolMessage(content="result", tool_call_id="call_1")])
    assert out[0]["tool_call_id"] == "call_1"


def test_an_assistant_turn_with_only_tool_calls_sends_null_content():
    """Some gateways reject "" but accept null; this is the shape that survives both."""
    from langchain_core.messages import AIMessage

    msg = AIMessage(
        content="",
        additional_kwargs={"tool_calls": [{"id": "1", "function": {"name": "f", "arguments": "{}"}}]},
    )
    out = to_litellm_messages([msg])
    assert out[0]["content"] is None
    assert out[0]["tool_calls"]


def test_content_text_flattens_every_shape_providers_return():
    assert content_text(None) == ""
    assert content_text("plain") == "plain"
    assert content_text({"text": "dict-text"}) == "dict-text"
    assert content_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    # An image block contributes nothing: base64 in a text stream is noise.
    assert content_text([{"type": "image_url", "image_url": {"url": "data:..."}}]) == ""


def test_provider_tool_calls_normalize_to_openai_shape():
    class Entry:
        class function:
            name = "f"
            arguments = "{}"

        id = "call_1"

    calls = tool_calls_from(type("M", (), {"tool_calls": [Entry()]})())
    assert calls == [
        {"id": "call_1", "type": "function", "function": {"name": "f", "arguments": "{}"}}
    ]
