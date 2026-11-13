from pathlib import Path

import pytest

from companion.adapters.llm.router import LLMRouter

ROUTING = Path(__file__).resolve().parents[1] / "config" / "llm" / "routing.yaml"


def test_companion_chat_chain_is_ordered_and_uses_env_names_only():
    """断言的是配置的**结构**，不是具体模型名：换供应商不该让测试失败，
    但「有序的两级故障转移」「只引用环境变量、不写死密钥」必须一直成立。"""
    chain = LLMRouter(ROUTING, environ={}).chain("companion_chat")
    assert len(chain) >= 2
    assert len({e.model for e in chain}) == len(chain)      # 两级不能是同一个模型
    for endpoint in chain:
        assert endpoint.model and endpoint.provider
        assert endpoint.api_base_env == "COMPANION_LLM_API_BASE"
        assert endpoint.api_key_env == "COMPANION_LLM_API_KEY"


def test_unset_override_keeps_the_committed_chain():
    # 没有 .env 的检出：变量未设置，用 yaml 里提交的模型名（不是空，也不是字面的变量名）。
    chain = LLMRouter(ROUTING, environ={}).chain("companion_chat")
    assert [e.model for e in chain] == ["doubao-seed-2-1-pro-260915", "doubao-seed-2-1-lite-260915"]


def test_override_replaces_models_in_order_and_keeps_tuning():
    env = {"COMPANION_LLM_MODEL_COMPANION_CHAT": "openai/gpt-x,openai/glm-y"}
    chain = LLMRouter(ROUTING, environ=env).chain("companion_chat")
    assert [e.model for e in chain] == ["openai/gpt-x", "openai/glm-y"]
    assert [e.timeout_sec for e in chain] == [60, 60]         # 调优沿用 yaml 对应位置


def test_override_longer_than_yaml_reuses_last_policy():
    # yaml 的 memory_extract 只有 1 跳、带 reasoning_effort=none；变量给 3 跳，多出的两跳沿用同一策略。
    env = {"COMPANION_LLM_MODEL_MEMORY_EXTRACT": "a,b,c"}
    chain = LLMRouter(ROUTING, environ=env).chain("memory_extract")
    assert [e.model for e in chain] == ["a", "b", "c"]
    assert all(e.reasoning_effort == "none" for e in chain)
    assert all(e.extra_body == {"thinking": {"type": "disabled"}} for e in chain)


def test_override_ignores_blank_items_and_whitespace():
    env = {"COMPANION_LLM_MODEL_COMPANION_REWRITE": " a , ,b "}
    assert [e.model for e in LLMRouter(ROUTING, environ=env).chain("companion_rewrite")] == ["a", "b"]


def test_empty_override_is_treated_as_unset():
    env = {"COMPANION_LLM_MODEL_COMPANION_CHAT": "   "}
    base = LLMRouter(ROUTING, environ={}).chain("companion_chat")
    assert [e.model for e in LLMRouter(ROUTING, environ=env).chain("companion_chat")] == [e.model for e in base]


def test_override_for_unknown_scenario_fails_loudly():
    # 拼错场景名：变量设了却没生效，必须报错，而不是悄悄继续跑旧模型。
    env = {"COMPANION_LLM_MODEL_COMPANION_CHAT_TYPO": "x"}
    with pytest.raises(ValueError, match="COMPANION_LLM_MODEL_COMPANION_CHAT_TYPO"):
        LLMRouter(ROUTING, environ=env)


def test_memory_extract_disables_reasoning():
    endpoint = LLMRouter(ROUTING, environ={}).chain("memory_extract")[0]
    assert endpoint.reasoning_effort == "none"
    assert endpoint.extra_body == {"thinking": {"type": "disabled"}}


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        LLMRouter(ROUTING, environ={}).chain("no_such_scenario")


def test_empty_scenario_is_rejected(tmp_path):
    bad = tmp_path / "routing.yaml"
    bad.write_text("scenarios:\n  empty: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        LLMRouter(bad, environ={})
