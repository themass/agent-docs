"""Fallback chain shape: every endpoint but the last must be a key in the map.

Regression for a real incident: `router_for` used to build a single flat
fallback entry `{primary: rest}`. litellm's fallback lookup keys strictly on
whichever model just failed, not the original primary, so a flat map only
ever covers the first hop — once the *second* endpoint in a 3+ endpoint chain
also failed, litellm found no key for it and raised `jc_invalid_response: ...
No fallback model group found for original model_group=writer-1`, even though
a third endpoint was configured and had never been tried. This test does not
hit any network; it only asserts the shape `router_for` hands to `litellm.Router`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from jc.llm import transport as transport_module


@dataclass(frozen=True, slots=True)
class _FakeEndpoint:
    model: str
    api_base_env: str = "FAKE_BASE"
    api_key_env: str = "FAKE_KEY"
    timeout_sec: int = 60
    temperature: float = 0.1
    provider: str | None = "gateway"
    reasoning_effort: str | None = None
    max_tokens: int | None = None
    extra_body: dict[str, object] | None = None


class _FakeLLMRouter:
    """Three-endpoint chain, all credentials present."""

    def chain_for(self, scenario: str) -> list[_FakeEndpoint]:
        assert scenario == "writer"
        return [
            _FakeEndpoint("openai/gpt-6-1-sol"),
            _FakeEndpoint("openai/claude-haiku-5-5"),
            _FakeEndpoint("openai/deepseek-v4-flash"),
        ]

    def credentials_for(self, endpoint: _FakeEndpoint) -> tuple[str, str]:
        return "https://fake.gateway/v1", "fake-key"


@pytest.fixture(autouse=True)
def _clear_cache():
    transport_module.clear_router_cache()
    yield
    transport_module.clear_router_cache()


def test_fallback_map_has_one_entry_per_position_not_one_flat_entry(monkeypatch):
    monkeypatch.setattr(
        "jc.llm.router.get_llm_router", lambda: _FakeLLMRouter()
    )

    transport = transport_module.router_for("writer")

    fallbacks = transport.router.fallbacks
    assert fallbacks is not None

    # Every endpoint except the last must appear as a key somewhere in the
    # map, with everything after it as the value. A flat {primary: rest} map
    # would only satisfy this for aliases[0] and leave aliases[1] unresolved —
    # which is exactly the bug: litellm has nowhere to go once the *second*
    # endpoint fails too.
    aliases = ["writer-0", "writer-1", "writer-2"]
    by_key = {}
    for entry in fallbacks:
        assert isinstance(entry, dict) and len(entry) == 1
        key, value = next(iter(entry.items()))
        by_key[key] = value

    for position, alias in enumerate(aliases[:-1]):
        assert alias in by_key, (
            f"{alias} has no fallback entry — if it fails after being "
            "reached via fallback, litellm has no further endpoint to try"
        )
        assert by_key[alias] == aliases[position + 1 :]

    assert aliases[-1] not in by_key, "the last endpoint must not have its own fallback entry"


def test_single_endpoint_scenario_has_no_fallbacks(monkeypatch):
    class _SingleEndpointRouter(_FakeLLMRouter):
        def chain_for(self, scenario: str) -> list[_FakeEndpoint]:
            return [_FakeEndpoint("openai/qwen-vl-ocr", provider="vision")]

    monkeypatch.setattr(
        "jc.llm.router.get_llm_router", lambda: _SingleEndpointRouter()
    )

    transport = transport_module.router_for("vision")

    assert transport.router.fallbacks is None


def test_router_for_propagates_endpoint_generation_policy(monkeypatch):
    from jc.llm.transport import router_for

    class PolicyRouter(_FakeLLMRouter):
        def chain_for(self, scenario):
            return [
                _FakeEndpoint(
                    "openai/structured",
                    reasoning_effort="none",
                    max_tokens=8192,
                    extra_body={"thinking": {"type": "disabled"}},
                )
            ]

    monkeypatch.setattr("jc.llm.router.get_llm_router", lambda: PolicyRouter())
    transport = router_for("writer")
    params = transport.deployments[0]["litellm_params"]
    assert params["reasoning_effort"] == "none"
    assert params["max_tokens"] == 8192
    assert params["extra_body"] == {"thinking": {"type": "disabled"}}
