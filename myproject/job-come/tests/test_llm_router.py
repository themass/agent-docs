"""Tests for LLM router config loading."""

from pathlib import Path

from jobcome.llm.router import LLMRouter


def test_llm_router_loads_scenarios() -> None:
    path = Path(__file__).resolve().parents[1] / "deploy" / "llm" / "routing.yaml"
    router = LLMRouter(path)
    assert "ingest_fast" in router._scenarios
    assert len(router._scenarios["ingest_fast"]) >= 1
    models = {ep.model for chain in router._scenarios.values() for ep in chain}
    assert "openai/bt-deepseek-v4-flash" in models
    assert "openai/bt-deepseek-v4-pro" in models
    assert "openai/mt-gpt-5-6-terra" in models
    assert "openai/mt-gpt-6-astra" in models
    assert router._scenarios["flash"][0].model.endswith("bt-deepseek-v4-flash")
    assert router._scenarios["writer"][0].model.endswith("bt-deepseek-v4-pro")
    assert router._scenarios["coach"][0].model.endswith("mt-gpt-5-6-terra")
