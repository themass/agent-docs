"""Tests for LLM router config loading."""

from pathlib import Path

from jc.llm.router import LLMRouter


def test_llm_router_loads_scenarios() -> None:
    path = Path(__file__).resolve().parents[1] / ".." / "agent" / "llm" / "routing.yaml"
    router = LLMRouter(path)
    assert "ingest_fast" in router._scenarios
    assert len(router._scenarios["ingest_fast"]) >= 1
    models = {ep.model for chain in router._scenarios.values() for ep in chain}
    assert "openai/deepseek-v4-flash" in models
    assert "openai/claude-haiku-5-5" in models
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
