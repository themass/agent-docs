"""A gateway-locked model must receive `reasoning_effort: none` with tools.

Measured against the live gateway on 2026-11-18, `gpt-6-luna` refuses function
tools while any reasoning mode is active, and the streaming failure has the
same silent shape as the temperature lock that started this:

    tools, reasoning at gateway default  ->  HTTP 200, ZERO SSE events
    tools + reasoning_effort=low         ->  HTTP 200, ZERO SSE events
    tools + thinking body flags          ->  HTTP 200, ZERO events (flags ignored)
    tools + reasoning_effort=none        ->  HTTP 200, finish_reason=tool_calls

The non-streaming twin states the rule outright: HTTP 500 "Function tools with
reasoning_effort are not supported for gpt-6-luna". The agent loop sends tools
on every turn, so a chat model that never unlocks becomes a chat that opens
with 200 and never answers — which is what prod did AFTER the temperature fix
shipped. glm-5.3-flash, gpt-6-sol and deepseek-v4-pro stream tool calls with
reasoning untouched, so the rule is per-model, not per-gateway.

Like temperature, the fix is chain-level rather than per-deployment: litellm
merges call-level params over every deployment's, so the request builder —
not the endpoint config — has to decide, and it decides per request shape:
a tools-free call on the same chain keeps its configured thinking.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from jc.llm.chat_litellm import ChatLiteLLMRouter
from jc.llm.router import LLMRouter, ModelEndpoint
from jc.llm.transport import ScenarioTransport, router_for, tools_require_reasoning_off

LOCKED = "openai/gpt-6-luna"
UNLOCKED = "openai/glm-5.3-flash"
TOOLS = [{
    "type": "function",
    "function": {
        "name": "jc_echo",
        "description": "echo a string",
        "parameters": {"type": "object", "properties": {"s": {"type": "string"}}},
    },
}]


# -- the table itself ---------------------------------------------------------


def test_the_tools_locked_model_is_recognized_in_both_spellings():
    assert tools_require_reasoning_off(LOCKED)
    assert tools_require_reasoning_off("gpt-6-luna")


def test_the_tools_unlocked_models_are_left_alone():
    # The reject side: forcing `none` on a model that streams tools with
    # thinking would silently lobotomize every healthy chain on the gateway.
    assert not tools_require_reasoning_off(UNLOCKED)
    assert not tools_require_reasoning_off("glm-5.3-flash")
    assert not tools_require_reasoning_off("gpt-6-sol")
    assert not tools_require_reasoning_off("deepseek-v4-pro")


# -- chain construction --------------------------------------------------------


def _endpoint(model: str) -> ModelEndpoint:
    return ModelEndpoint(
        model=model,
        api_base_env="TEST_LLM_BASE",
        api_key_env="TEST_LLM_KEY",
        timeout_sec=30,
        temperature=0.1,
    )


@pytest.fixture
def fake_gateway(monkeypatch):
    def install(*models: str) -> None:
        chain = [_endpoint(m) for m in models]
        monkeypatch.setattr(
            "jc.llm.router.get_llm_router",
            lambda: SimpleNamespace(
                chain_for=lambda scenario: list(chain),
                credentials_for=lambda endpoint: ("https://gateway.test/v1", "sk-test"),
            ),
        )

    return install


def test_a_tools_locked_chain_is_flagged_whatever_position(fake_gateway):
    fake_gateway(LOCKED, UNLOCKED)
    assert router_for("coach").reasoning_off_forced is True
    fake_gateway(UNLOCKED, LOCKED)
    assert router_for("reviewer").reasoning_off_forced is True


def test_an_unlocked_chain_is_not_flagged(fake_gateway):
    # The reject side: nothing on a clean chain may start forcing reasoning off.
    fake_gateway(UNLOCKED, "openai/gpt-6-sol")
    assert router_for("writer").reasoning_off_forced is False


def test_the_locked_deployment_itself_is_not_rewritten(fake_gateway):
    # The scalpel: the request builder decides per request shape. Injecting
    # `none` into the deployment would also change tools-free turns, which was
    # never measured as wanted — the gateway streams plain text fine on luna
    # with reasoning untouched.
    fake_gateway(LOCKED, UNLOCKED)
    t = router_for("coach")
    assert "reasoning_effort" not in t.deployments[0]["litellm_params"]
    assert "reasoning_effort" not in t.deployments[1]["litellm_params"]


# -- request construction: the deterministic services -------------------------


def _router(tmp_path, monkeypatch) -> LLMRouter:
    for name in list(__import__("os").environ):
        if name.startswith("JC_LLM_MODEL_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JC_LLM_MODEL_COACH", UNLOCKED)
    path = tmp_path / "routing.yaml"
    path.write_text("scenarios:\n  coach:\n    - timeout_sec: 60\n", encoding="utf-8")
    return LLMRouter(path)


def test_a_forced_chain_with_tools_gets_reasoning_off(tmp_path, monkeypatch):
    # `extra_body`, not top-level: litellm drops `reasoning_effort` from the
    # body it posts for gateway models it cannot classify (measured 2026-11-18
    # via its own curl-equivalent debug output). extra_body survives the SDK.
    kwargs = _router(tmp_path, monkeypatch)._request_kwargs(
        "coach-0", messages=[], tools=TOOLS, response_format=None,
        temperature=None, max_tokens=None, scenario="coach", caller="test",
        reasoning_off_forced=True,
    )
    assert kwargs["extra_body"] == {"reasoning_effort": "none"}
    assert "reasoning_effort" not in kwargs


def test_a_forced_chain_without_tools_keeps_its_thinking(tmp_path, monkeypatch):
    # The reject side: flash/ingest-style calls on the same chain must not be
    # silently retuned; only the tools shape is poison.
    kwargs = _router(tmp_path, monkeypatch)._request_kwargs(
        "coach-0", messages=[], tools=None, response_format=None,
        temperature=None, max_tokens=None, scenario="coach", caller="test",
        reasoning_off_forced=True,
    )
    assert "extra_body" not in kwargs
    assert "reasoning_effort" not in kwargs


def test_an_unforced_chain_with_tools_is_untouched(tmp_path, monkeypatch):
    # The other reject side: healthy chains keep sending tools with no
    # reasoning parameter, exactly as before this fix.
    kwargs = _router(tmp_path, monkeypatch)._request_kwargs(
        "coach-0", messages=[], tools=TOOLS, response_format=None,
        temperature=None, max_tokens=None, scenario="coach", caller="test",
        reasoning_off_forced=False,
    )
    assert "reasoning_effort" not in kwargs


# -- request construction: the agent harness ------------------------------------


def _locked_transport(**kw) -> ScenarioTransport:
    return ScenarioTransport(
        router=None, primary="coach-0", skipped=(),
        reasoning_off_forced=True, **kw
    )


def test_the_harness_forces_off_when_it_sends_tools(monkeypatch):
    # The prod shape: agent loop, tools bound, DeerFlow passing reasoning_effort.
    llm = ChatLiteLLMRouter(model="coach", reasoning_effort="low")
    monkeypatch.setattr(llm, "_transport", _locked_transport)
    payload = llm._request_kwargs([HumanMessage(content="hi")], None, tools=TOOLS)
    assert payload["tools"] == TOOLS
    assert payload["extra_body"] == {"reasoning_effort": "none"}


def test_the_harness_keeps_thinking_on_a_tools_free_call(monkeypatch):
    # Reject side: plain generate on the same locked chain keeps its effort.
    llm = ChatLiteLLMRouter(model="coach", reasoning_effort="low")
    monkeypatch.setattr(llm, "_transport", _locked_transport)
    payload = llm._request_kwargs([HumanMessage(content="hi")], None)
    assert payload["reasoning_effort"] == "low"


def test_the_harness_on_a_clean_chain_is_untouched(monkeypatch):
    llm = ChatLiteLLMRouter(model="coach", reasoning_effort="low")
    clean = ScenarioTransport(
        router=None, primary="coach-0", skipped=(), reasoning_off_forced=False
    )
    monkeypatch.setattr(llm, "_transport", lambda: clean)
    payload = llm._request_kwargs([HumanMessage(content="hi")], None, tools=TOOLS)
    assert payload["reasoning_effort"] == "low"
    assert "extra_body" not in payload


def test_the_forced_unlock_survives_a_config_extra_body(monkeypatch):
    # DeerFlow's thinking templates ship their own extra_body; the unlock must
    # merge into it, not be replaced by it.
    llm = ChatLiteLLMRouter(
        model="coach", extra_body={"thinking": {"type": "enabled"}}
    )
    monkeypatch.setattr(llm, "_transport", _locked_transport)
    payload = llm._request_kwargs([HumanMessage(content="hi")], None, tools=TOOLS)
    assert payload["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "none",
    }
