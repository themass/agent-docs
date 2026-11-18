"""A gateway-locked model must never receive an explicit temperature.

Measured against the live gateway on 2026-11-18, `gpt-6-luna` rejects every
explicit temperature except 1 — and the two shapes of rejection differ in the
way that turned it into a P0:

    non-streaming + temperature=0.1  ->  HTTP 500, fallback moves on (noisy)
    STREAMING     + temperature=0.1  ->  HTTP 200, ZERO chunks (silent)

The streaming shape is the one that hurts: langchain raises "No generations
found in stream", the agent's error middleware retries the same poisoned
endpoint three times, and the user's turn opens with 200 and never answers.
`drop_params` cannot save this — the gateway answers 200, so litellm has
nothing it would consider dropping.

The rule that follows is chain-level, not endpoint-level: litellm merges
call-level params over every deployment's, so one caller passing `temperature=
0.2` re-poisons the locked hop even after the deployment itself was cleaned.
Every request builder therefore asks the transport, not the caller.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

from jc.llm import transport as transport_mod
from jc.llm.chat_litellm import ChatLiteLLMRouter
from jc.llm.router import LLMRouter, ModelEndpoint
from jc.llm.transport import ScenarioTransport, is_temperature_locked, router_for

LOCKED = "openai/gpt-6-luna"
UNLOCKED = "openai/glm-5.3-flash"


# -- the table itself ---------------------------------------------------------


def test_the_locked_model_is_recognized_in_both_spellings():
    # .env writes `openai/gpt-6-luna`; gateways echo the bare slug.
    assert is_temperature_locked(LOCKED)
    assert is_temperature_locked("gpt-6-luna")


def test_the_unlocked_models_keep_their_temperature():
    # The reject side: over-stripping would silently retune every healthy
    # model on the chain, and 0.1 was measured, not guessed.
    assert not is_temperature_locked(UNLOCKED)
    assert not is_temperature_locked("glm-5.3-flash")
    assert not is_temperature_locked("gpt-6-sol")


# -- deployment construction ---------------------------------------------------


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
    """Install a chain for scenario `coach` without touching settings or .env."""

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


def test_the_locked_hop_gets_no_deployment_temperature(fake_gateway):
    fake_gateway(LOCKED, UNLOCKED)
    t = router_for("coach")
    assert t.temperature_locked is True
    locked, unlocked = t.deployments
    assert "temperature" not in locked["litellm_params"]
    # The unlocked hop keeps its measured tuning. The fix is a scalpel, not a
    # blanket: removing 0.1 from glm would be an unmeasured behavior change.
    assert unlocked["litellm_params"]["temperature"] == 0.1


def test_an_all_unlocked_chain_is_left_alone(fake_gateway):
    # The reject side: today's production chains that never mention luna must
    # construct byte-identical deployments to before this fix.
    fake_gateway(UNLOCKED, "openai/deepseek-v4-pro")
    t = router_for("coach")
    assert t.temperature_locked is False
    assert all(d["litellm_params"]["temperature"] == 0.1 for d in t.deployments)


def test_a_locked_second_hop_marks_the_whole_chain(fake_gateway):
    # Position matters not at all: litellm merges call params over EVERY
    # deployment, so a locked understudy poisons a request built for the lead.
    fake_gateway(UNLOCKED, LOCKED)
    t = router_for("coach")
    assert t.temperature_locked is True
    assert "temperature" not in t.deployments[1]["litellm_params"]


# -- request construction: the deterministic services --------------------------


def _router(tmp_path, monkeypatch) -> LLMRouter:
    # Names come from `.env`, tuning from the file — same split production runs.
    # Other scenarios' variables must go first: an earlier test in this file
    # loads the repo `.env`, and the router rejects `JC_LLM_MODEL_*` names the
    # routing file does not declare.
    for name in list(os.environ):
        if name.startswith("JC_LLM_MODEL_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JC_LLM_MODEL_COACH", UNLOCKED)
    path = tmp_path / "routing.yaml"
    path.write_text("scenarios:\n  coach:\n    - timeout_sec: 60\n", encoding="utf-8")
    return LLMRouter(path)


def test_a_locked_chain_drops_the_callers_temperature(tmp_path, monkeypatch):
    kwargs = _router(tmp_path, monkeypatch)._request_kwargs(
        "coach-0", messages=[], tools=None, response_format=None,
        temperature=0.2, max_tokens=None, scenario="coach", caller="test",
        temperature_locked=True,
    )
    assert "temperature" not in kwargs


def test_an_unlocked_chain_honors_the_callers_temperature(tmp_path, monkeypatch):
    # The reject side: fit_score's 0.0 and the writer's 0.2 must survive on
    # chains that can take them.
    kwargs = _router(tmp_path, monkeypatch)._request_kwargs(
        "coach-0", messages=[], tools=None, response_format=None,
        temperature=0.2, max_tokens=None, scenario="coach", caller="test",
        temperature_locked=False,
    )
    assert kwargs["temperature"] == 0.2


# -- request construction: the agent harness ------------------------------------


def test_the_harness_omits_temperature_on_a_locked_chain(monkeypatch):
    llm = ChatLiteLLMRouter(model="coach", temperature=0.2)
    locked = ScenarioTransport(
        router=None, primary="coach-0", skipped=(), temperature_locked=True
    )
    monkeypatch.setattr(llm, "_transport", lambda: locked)
    payload = llm._request_kwargs([HumanMessage(content="hi")], None)
    assert "temperature" not in payload


def test_the_harness_keeps_temperature_on_an_unlocked_chain(monkeypatch):
    llm = ChatLiteLLMRouter(model="coach", temperature=0.2)
    unlocked = ScenarioTransport(
        router=None, primary="coach-0", skipped=(), temperature_locked=False
    )
    monkeypatch.setattr(llm, "_transport", lambda: unlocked)
    payload = llm._request_kwargs([HumanMessage(content="hi")], None)
    assert payload["temperature"] == 0.2
