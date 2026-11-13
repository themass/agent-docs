import pytest

from companion.adapters.llm.router import LLMRouter
from companion.paths import LLM_ROUTING_PATH

ROUTING = LLM_ROUTING_PATH

#: 每个场景都给出模型链；模型名只从环境来，测试必须显式提供。
ALL_SCENARIOS = {
    "COMPANION_LLM_MODEL_COMPANION_CHAT": "a,b",
    "COMPANION_LLM_MODEL_MEMORY_EXTRACT": "c",
    "COMPANION_LLM_MODEL_SESSION_SUMMARIZE": "c",
    "COMPANION_LLM_MODEL_COMPANION_REWRITE": "c",
}


def test_companion_chat_chain_is_ordered_and_uses_env_names_only():
    """断言的是配置的**结构**，不是具体模型名：换供应商不该让测试失败，
    但「有序的两级故障转移」「只引用环境变量、不写死密钥」必须一直成立。"""
    env = {"COMPANION_LLM_MODEL_COMPANION_CHAT": "first,second",
           "COMPANION_LLM_MODEL_MEMORY_EXTRACT": "cheap",
           "COMPANION_LLM_MODEL_SESSION_SUMMARIZE": "cheap",
           "COMPANION_LLM_MODEL_COMPANION_REWRITE": "cheap"}
    chain = LLMRouter(ROUTING, environ=env).chain("companion_chat")
    assert len(chain) >= 2
    assert len({e.model for e in chain}) == len(chain)      # 两级不能是同一个模型
    for endpoint in chain:
        assert endpoint.model and endpoint.provider
        assert endpoint.api_base_env == "COMPANION_LLM_API_BASE"
        assert endpoint.api_key_env == "COMPANION_LLM_API_KEY"


def test_model_names_come_only_from_env():
    # 模型名只有 .env 一个来源：变量没设就是错误，不会退回 yaml 里的默认值。
    with pytest.raises(ValueError, match="COMPANION_LLM_MODEL_COMPANION_CHAT"):
        LLMRouter(ROUTING, environ={})


def test_routing_yaml_must_not_name_any_model():
    # 提交的文件里不允许出现 model 字段——两处都能写就是「改了哪个生效说不清」。
    import yaml
    raw = yaml.safe_load(ROUTING.read_text(encoding="utf-8"))
    for scenario, entries in raw["scenarios"].items():
        for entry in entries:
            assert "model" not in entry, f"{scenario} 里还有 model 字段"


def test_override_replaces_models_in_order_and_keeps_tuning():
    env = {**ALL_SCENARIOS, "COMPANION_LLM_MODEL_COMPANION_CHAT": "openai/gpt-x,openai/glm-y"}
    chain = LLMRouter(ROUTING, environ=env).chain("companion_chat")
    assert [e.model for e in chain] == ["openai/gpt-x", "openai/glm-y"]
    assert [e.timeout_sec for e in chain] == [60, 60]         # 调优沿用 yaml 对应位置


def test_override_longer_than_yaml_reuses_last_policy():
    # yaml 的 memory_extract 只有 1 跳、带 reasoning_effort=none；变量给 3 跳，多出的两跳沿用同一策略。
    env = {**ALL_SCENARIOS, "COMPANION_LLM_MODEL_MEMORY_EXTRACT": "a,b,c"}
    chain = LLMRouter(ROUTING, environ=env).chain("memory_extract")
    assert [e.model for e in chain] == ["a", "b", "c"]
    assert all(e.reasoning_effort == "none" for e in chain)
    assert all(e.extra_body == {"thinking": {"type": "disabled"}} for e in chain)


def test_override_ignores_blank_items_and_whitespace():
    env = {**ALL_SCENARIOS, "COMPANION_LLM_MODEL_COMPANION_REWRITE": " a , ,b "}
    assert [e.model for e in LLMRouter(ROUTING, environ=env).chain("companion_rewrite")] == ["a", "b"]


def test_blank_override_is_rejected():
    # 设了但全是空白/逗号 = 没给模型，同样报错而不是悄悄用旧的。
    env = {**ALL_SCENARIOS, "COMPANION_LLM_MODEL_COMPANION_CHAT": " , , "}
    with pytest.raises(ValueError, match="COMPANION_LLM_MODEL_COMPANION_CHAT"):
        LLMRouter(ROUTING, environ=env)


def test_override_for_unknown_scenario_fails_loudly():
    # 拼错场景名：变量设了却没生效，必须报错，而不是悄悄继续跑旧模型。
    env = {"COMPANION_LLM_MODEL_COMPANION_CHAT_TYPO": "x"}
    with pytest.raises(ValueError, match="COMPANION_LLM_MODEL_COMPANION_CHAT_TYPO"):
        LLMRouter(ROUTING, environ=env)


def test_memory_extract_disables_reasoning():
    endpoint = LLMRouter(ROUTING, environ=ALL_SCENARIOS).chain("memory_extract")[0]
    assert endpoint.reasoning_effort == "none"
    assert endpoint.extra_body == {"thinking": {"type": "disabled"}}


def test_unknown_scenario_raises():
    with pytest.raises(KeyError):
        LLMRouter(ROUTING, environ=ALL_SCENARIOS).chain("no_such_scenario")


def test_empty_scenario_is_rejected(tmp_path):
    bad = tmp_path / "routing.yaml"
    bad.write_text("scenarios:\n  empty: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        LLMRouter(bad, environ=ALL_SCENARIOS)
