"""Model names come from `.env`; tuning stays in `routing.yaml`.

The split matters because the two halves change for different reasons. A timeout
or an output ceiling was measured against the gateway once and rarely moves; the
model in a chain is what an operator swaps when a provider degrades. Before this,
each scenario repeated the same model, so switching the workhorse meant editing
five chains in a file that also holds the measurements.
"""

from __future__ import annotations

import pytest

from jc.llm.router import LLMRouter

ROUTING = """
scenarios:
  coach:
    - model: openai/committed-lead
      timeout_sec: 180
  writer:
    - model: openai/committed-lead
      timeout_sec: 180
    - model: openai/committed-backup
      timeout_sec: 60
      reasoning_effort: none
"""


def _router(tmp_path, text: str = ROUTING) -> LLMRouter:
    path = tmp_path / "routing.yaml"
    path.write_text(text, encoding="utf-8")
    return LLMRouter(path)


def test_without_the_variable_the_committed_chain_runs(tmp_path, monkeypatch):
    """A checkout with no `.env` must still work — the yaml stays a valid config."""
    monkeypatch.delenv("JC_LLM_MODEL_COACH", raising=False)
    chain = _router(tmp_path).chain_for("coach")
    assert [e.model for e in chain] == ["openai/committed-lead"]


def test_the_variable_replaces_the_model_and_keeps_the_policy(tmp_path, monkeypatch):
    """The whole point: swap the name, keep the measured timeout."""
    monkeypatch.setenv("JC_LLM_MODEL_COACH", "openai/gpt-6-luna")
    chain = _router(tmp_path).chain_for("coach")
    assert [e.model for e in chain] == ["openai/gpt-6-luna"]
    assert chain[0].timeout_sec == 180


def test_a_comma_separated_chain_keeps_one_policy_per_position(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "JC_LLM_MODEL_WRITER", "openai/first-choice, openai/second-choice"
    )
    chain = _router(tmp_path).chain_for("writer")
    assert [e.model for e in chain] == ["openai/first-choice", "openai/second-choice"]
    # Position 1 keeps its own tuning (60s, no reasoning), not position 0's.
    assert chain[1].timeout_sec == 60
    assert chain[1].reasoning_effort == "none"


def test_a_longer_chain_repeats_the_last_policy(tmp_path, monkeypatch):
    """Adding a third hop in `.env` must not require inventing tuning for it."""
    monkeypatch.setenv("JC_LLM_MODEL_COACH", "openai/a,openai/b,openai/c")
    chain = _router(tmp_path).chain_for("coach")
    assert [e.model for e in chain] == ["openai/a", "openai/b", "openai/c"]
    assert [e.timeout_sec for e in chain] == [180, 180, 180]


def test_a_typo_in_the_variable_name_fails_loudly(tmp_path, monkeypatch):
    """Silently ignoring it is the failure mode: the operator believes it took."""
    monkeypatch.setenv("JC_LLM_MODEL_COACHX", "openai/whatever")
    with pytest.raises(ValueError, match="does not match any scenario"):
        _router(tmp_path)


def test_an_empty_value_falls_back_to_the_committed_chain(tmp_path, monkeypatch):
    monkeypatch.setenv("JC_LLM_MODEL_COACH", "   ")
    chain = _router(tmp_path).chain_for("coach")
    assert [e.model for e in chain] == ["openai/committed-lead"]


def test_one_variable_does_not_disturb_the_other_scenarios(tmp_path, monkeypatch):
    monkeypatch.setenv("JC_LLM_MODEL_COACH", "openai/only-coach")
    router = _router(tmp_path)
    assert [e.model for e in router.chain_for("coach")] == ["openai/only-coach"]
    assert [e.model for e in router.chain_for("writer")][0] == "openai/committed-lead"


def test_the_real_config_still_parses_and_every_scenario_has_a_chain():
    """Guards the committed routing.yaml, not a fixture: a deleted scenario would
    otherwise only surface as a 500 on the feature that used it."""
    from jc.agent.roles import roles
    from jc.llm.router import get_llm_router

    router = get_llm_router()
    needed = {role_.scenario for role_ in roles().values()}
    for scenario in sorted(needed):
        assert router.chain_for(scenario), f"scenario {scenario!r} resolved to an empty chain"
