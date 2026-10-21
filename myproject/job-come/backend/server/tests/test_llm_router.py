"""Tests for LLM router config loading."""

from pathlib import Path

from jc.llm.router import LLMRouter


def test_llm_router_loads_scenarios() -> None:
    path = Path(__file__).resolve().parents[1] / ".." / "agent" / "llm" / "routing.yaml"
    router = LLMRouter(path)
    assert "ingest_fast" in router._scenarios
    assert len(router._scenarios["ingest_fast"]) >= 1
    models = {ep.model for chain in router._scenarios.values() for ep in chain}
    assert {
        "openai/deepseek-v4-flash",
        "openai/glm-5-3-flash",
        "openai/doubao-seed-2-0-lite-260215",
    } <= {endpoint.model for endpoint in router._scenarios["ingest_fast"]}
    assert "openai/gpt-6-1-sol" in models
    assert "openai/qwen-vl-ocr" in models
    assert router._scenarios["flash"][0].model.endswith("deepseek-v4-flash")
    assert router._scenarios["writer"][0].model.endswith("gpt-6-1-sol")
    assert router._scenarios["coach"][0].model.endswith("gpt-6-1-sol")
    vision = router._scenarios["vision"][0]
    assert vision.provider == "vision"
    assert vision.api_key_env == "JC_LLM_VISION_API_KEY"
    coach = router._scenarios["coach"][0]
    assert coach.provider == "gateway"
    assert coach.api_base_env == "JC_LLM_API_BASE"


def test_llm_router_per_model_provider(tmp_path: Path) -> None:
    cfg = tmp_path / "routing.yaml"
    cfg.write_text(
        """
providers:
  a:
    api_base_env: JC_LLM_A_BASE
    api_key_env: JC_LLM_A_KEY
  b:
    api_base_env: JC_LLM_B_BASE
    api_key_env: JC_LLM_B_KEY
scenarios:
  flash:
    - model: openai/m1
      provider: a
    - model: openai/m2
      provider: b
defaults:
  provider: a
""",
        encoding="utf-8",
    )
    router = LLMRouter(cfg)
    chain = router._scenarios["flash"]
    assert chain[0].api_key_env == "JC_LLM_A_KEY"
    assert chain[1].api_base_env == "JC_LLM_B_BASE"


def test_ingest_chain_has_explicit_non_reasoning_policy() -> None:
    path = Path(__file__).resolve().parents[1] / ".." / "agent" / "llm" / "routing.yaml"
    router = LLMRouter(path)
    for endpoint in router._scenarios["ingest_fast"]:
        assert endpoint.reasoning_effort == "none"
        assert endpoint.max_tokens == 100000
        assert endpoint.extra_body == {"thinking": {"type": "disabled"}}


def test_agent_chains_do_not_inherit_ingestion_reasoning_policy() -> None:
    path = Path(__file__).resolve().parents[1] / ".." / "agent" / "llm" / "routing.yaml"
    router = LLMRouter(path)
    assert router._scenarios["coach"][0].reasoning_effort is None
    assert router._scenarios["coach"][0].extra_body is None
    assert router._scenarios["coach"][0].max_tokens == 100000
    assert router._scenarios["writer"][0].max_tokens == 100000


def test_output_policy_defaults_overrides_and_positive_validation(tmp_path):
    import pytest

    config = tmp_path / "routing.yaml"
    config.write_text("defaults: {max_tokens: 100000}\nscenarios:\n  task:\n"
                      "    - model: openai/primary\n"
                      "    - model: openai/fallback\n      max_tokens: 32000\n")
    primary, fallback = LLMRouter(config).chain_for("task")
    assert primary.max_tokens == 100000
    assert fallback.max_tokens == 32000
    config.write_text("defaults: {max_tokens: 0}\nscenarios: {}\n")
    with pytest.raises(ValueError, match="max_tokens must be positive"):
        LLMRouter(config)
