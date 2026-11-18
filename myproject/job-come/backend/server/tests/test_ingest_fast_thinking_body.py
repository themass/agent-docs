"""ingest_fast hop tuning must not send `thinking` to models that reject it.

R3 P0: `POST /jobs/.../parse` 500 because
  ingest_fast-0 (glm-5.3-flash) → empty/unparseable JSON → failover
  ingest_fast-1 (gpt-6-luna)    → `Unknown parameter: 'thinking'`

`routing.yaml` put DeepSeek-style `extra_body.thinking` on every ingest_fast
position. Position 1 in the live chain is gpt-6-luna, which rejects that body
field outright. Failover then has nowhere to go, so a recoverable primary miss
becomes a user-visible 500.

`routing.example.yaml` already shows the intended shape (thinking only where
the hop needs the DeepSeek switch). The live file must match that contract:
hop 0 may carry `thinking: disabled`; hop 1 must not.
"""

from __future__ import annotations

import yaml

from jc.llm.router import LLMRouter
from jc.paths import agent_file


#: Every scenario the committed routing file declares — see test_llm_model_env.
COMMITTED_CHAINS = {
    "ingest_fast": "openai/glm-5.3-flash,openai/gpt-6-luna",
    "writer": "openai/a,openai/b",
    "coach": "openai/a,openai/b",
    "reviewer": "openai/a,openai/b",
    "vision": "openai/a,openai/b",
    "flash": "openai/a,openai/b",
}


def _live_ingest_chain(monkeypatch) -> list:
    for scenario, chain in COMMITTED_CHAINS.items():
        monkeypatch.setenv(f"JC_LLM_MODEL_{scenario.upper()}", chain)
    path = agent_file("llm", "routing.yaml")
    return LLMRouter(path).chain_for("ingest_fast")


def test_ingest_fast_fallback_hop_does_not_send_thinking_body(monkeypatch):
    chain = _live_ingest_chain(monkeypatch)
    assert len(chain) >= 2
    assert chain[1].extra_body is None or "thinking" not in (chain[1].extra_body or {})


def test_ingest_fast_still_disables_reasoning_on_every_hop(monkeypatch):
    """Reject side: dropping thinking must not re-enable hidden reasoning."""
    chain = _live_ingest_chain(monkeypatch)
    assert all(hop.reasoning_effort == "none" for hop in chain)


def test_live_routing_yaml_matches_example_on_ingest_fast_thinking():
    """Guard the checked-in files themselves — example already got this right."""
    live = yaml.safe_load(agent_file("llm", "routing.yaml").read_text(encoding="utf-8"))
    example = yaml.safe_load(
        agent_file("llm", "routing.example.yaml").read_text(encoding="utf-8")
    )
    live_hops = live["scenarios"]["ingest_fast"]
    example_hops = example["scenarios"]["ingest_fast"]
    assert len(live_hops) == len(example_hops)
    for index, (live_hop, example_hop) in enumerate(zip(live_hops, example_hops, strict=True)):
        live_thinking = (live_hop.get("extra_body") or {}).get("thinking")
        example_thinking = (example_hop.get("extra_body") or {}).get("thinking")
        assert live_thinking == example_thinking, (
            f"ingest_fast[{index}] thinking body diverges from routing.example.yaml"
        )
