from pathlib import Path

import pytest

from companion.adapters.llm.router import LLMRouter

ROUTING = Path(__file__).resolve().parents[1] / "config" / "llm" / "routing.yaml"


def test_companion_chat_chain_is_ordered_and_uses_env_names_only():
    """断言的是配置的**结构**，不是具体模型名：换供应商（2026-11-12 换到豆包方舟）不该让测试失败，
    但「有序的两级故障转移」「只引用环境变量、不写死密钥」必须一直成立。"""
    router = LLMRouter(ROUTING)
    chain = router.chain("companion_chat")
    assert len(chain) >= 2
    assert len({e.model for e in chain}) == len(chain)      # 两级不能是同一个模型
    for endpoint in chain:
        assert endpoint.model and endpoint.provider
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
