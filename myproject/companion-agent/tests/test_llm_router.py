from pathlib import Path

import pytest

from companion.llm.router import LLMRouter

ROUTING = Path(__file__).resolve().parents[1] / "config" / "llm" / "routing.yaml"


def test_companion_chat_chain_is_ordered_and_uses_env_names_only():
    router = LLMRouter(ROUTING)
    chain = router.chain("companion_chat")
    assert [e.model for e in chain] == [
        "openai/deepseek-v4-pro",
        "openai/deepseek-v4-flash",
    ]
    for endpoint in chain:
        assert endpoint.api_base_env == "COMPANION_LLM_API_BASE"
        assert endpoint.api_key_env == "COMPANION_LLM_API_KEY"


def test_memory_extract_disables_reasoning():
    endpoint = LLMRouter(ROUTING).chain("memory_extract")[0]
    assert endpoint.reasoning_effort == "none"
    assert endpoint.extra_body == {"thinking": {"type": "disabled"}}


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        LLMRouter(ROUTING).chain("no_such_scenario")


def test_empty_scenario_is_rejected(tmp_path):
    bad = tmp_path / "routing.yaml"
    bad.write_text("scenarios:\n  empty: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        LLMRouter(bad)
