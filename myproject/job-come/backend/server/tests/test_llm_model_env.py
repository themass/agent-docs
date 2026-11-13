"""Model names live only in `.env`; `routing.yaml` carries only per-position tuning.

The two halves change for different reasons. A timeout or output ceiling was
measured against the gateway once and rarely moves; the model in a chain is what
an operator swaps when a provider degrades. Keeping names in both places made
"which one is in effect" ambiguous, so names come from `.env` and nothing else.
"""

from __future__ import annotations

import pytest

from jc.llm.router import LLMRouter


def _router(tmp_path, text: str) -> LLMRouter:
    path = tmp_path / "routing.yaml"
    path.write_text(text, encoding="utf-8")
    return LLMRouter(path)


def _tuning_only(tmp_path, scenarios: str) -> LLMRouter:
    return _router(tmp_path, f"scenarios:\n{scenarios}")


TWO_POSITIONS = """  writer:
    - timeout_sec: 180
    - timeout_sec: 60
      reasoning_effort: none
"""


def test_the_names_come_from_env_and_the_tuning_from_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("JC_LLM_MODEL_WRITER", "openai/first,openai/second")
    chain = _tuning_only(tmp_path, TWO_POSITIONS).chain_for("writer")
    assert [e.model for e in chain] == ["openai/first", "openai/second"]
    # Position 1 keeps its own tuning, not position 0's.
    assert [e.timeout_sec for e in chain] == [180, 60]
    assert chain[1].reasoning_effort == "none"


def test_a_missing_variable_is_an_error_not_a_silent_default(tmp_path, monkeypatch):
    """A scenario with no models has nothing to call; failing at load beats 500s."""
    monkeypatch.delenv("JC_LLM_MODEL_WRITER", raising=False)
    with pytest.raises(ValueError, match="JC_LLM_MODEL_WRITER is required"):
        _tuning_only(tmp_path, TWO_POSITIONS)


def test_a_longer_chain_repeats_the_last_policy(tmp_path, monkeypatch):
    """Adding a third hop in `.env` must not require inventing tuning for it."""
    monkeypatch.setenv("JC_LLM_MODEL_WRITER", "openai/a,openai/b,openai/c")
    chain = _tuning_only(tmp_path, TWO_POSITIONS).chain_for("writer")
    assert [e.model for e in chain] == ["openai/a", "openai/b", "openai/c"]
    assert [e.timeout_sec for e in chain] == [180, 60, 60]


def test_a_typo_in_the_variable_name_fails_loudly(tmp_path, monkeypatch):
    """Silently ignoring it is the failure mode: the operator believes it took."""
    monkeypatch.setenv("JC_LLM_MODEL_WRITER", "openai/a")
    monkeypatch.setenv("JC_LLM_MODEL_WRITTER", "openai/typo")
    with pytest.raises(ValueError, match="does not match any scenario"):
        _tuning_only(tmp_path, TWO_POSITIONS)


def test_whitespace_around_a_comma_is_tolerated(tmp_path, monkeypatch):
    monkeypatch.setenv("JC_LLM_MODEL_WRITER", " openai/a , openai/b ")
    chain = _tuning_only(tmp_path, TWO_POSITIONS).chain_for("writer")
    assert [e.model for e in chain] == ["openai/a", "openai/b"]


def test_a_scenario_with_no_tuning_is_still_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JC_LLM_MODEL_WRITER", "openai/a")
    with pytest.raises(ValueError, match="has no entries"):
        _tuning_only(tmp_path, "  writer: []\n")


def test_one_variable_does_not_disturb_another_scenario(tmp_path, monkeypatch):
    monkeypatch.setenv("JC_LLM_MODEL_WRITER", "openai/only-writer")
    monkeypatch.setenv("JC_LLM_MODEL_COACH", "openai/only-coach")
    router = _tuning_only(
        tmp_path,
        "  writer:\n    - timeout_sec: 180\n  coach:\n    - timeout_sec: 180\n",
    )
    assert [e.model for e in router.chain_for("writer")] == ["openai/only-writer"]
    assert [e.model for e in router.chain_for("coach")] == ["openai/only-coach"]


#: Every scenario the committed routing file declares, with a chain to run it on.
#: These tests read the real file, and the test suite deliberately does not load
#: `backend/server/.env` (see conftest), so the names have to be supplied here.
COMMITTED_CHAINS = {
    "ingest_fast": "openai/a,openai/b",
    "writer": "openai/a,openai/b",
    "coach": "openai/a,openai/b",
    "reviewer": "openai/a,openai/b",
    "vision": "openai/a,openai/b",
    "flash": "openai/a,openai/b",
}


@pytest.fixture
def committed_env(monkeypatch):
    for scenario, chain in COMMITTED_CHAINS.items():
        monkeypatch.setenv(f"JC_LLM_MODEL_{scenario.upper()}", chain)
    return COMMITTED_CHAINS


def test_the_committed_routing_file_names_no_models(committed_env):
    """The regression this design exists to prevent: a second place naming a model.

    If someone adds `model:` back to the committed file, the code ignores it and
    the operator edits a setting that does nothing.
    """
    import yaml

    from jc.llm.router import get_llm_router
    from jc.paths import agent_file

    raw = yaml.safe_load(agent_file("llm", "routing.yaml").read_text(encoding="utf-8"))
    for scenario, entries in raw["scenarios"].items():
        for index, entry in enumerate(entries):
            assert "model" not in entry, (
                f"scenarios.{scenario}[{index}] names a model; names belong in "
                "JC_LLM_MODEL_* (.env) so there is exactly one source for them"
            )
    # And the real config still resolves, with names from the environment.
    assert get_llm_router().chain_for("coach")


def test_the_committed_routing_file_covers_every_scenario_a_role_uses(committed_env):
    """A scenario dropped from the file would surface as a 500 on its feature."""
    from jc.agent.roles import roles
    from jc.llm.router import get_llm_router

    router = get_llm_router()
    for scenario in sorted({r.scenario for r in roles().values()}):
        assert router.chain_for(scenario), f"scenario {scenario!r} resolved to an empty chain"
