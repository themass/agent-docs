"""Gateway pricing for models litellm does not know.

Why this exists: every model in `routing.yaml` is reached through a gateway under a
vendor-neutral name (`gpt-6-1-sol`, `deepseek-v4-flash`, ...), and none of those
names are in litellm's bundled price map. `litellm.completion_cost` therefore raised
for every call this product has ever made, `cost_micro_usd` swallowed it, and the
admin list's 花费 column was empty for every row — not wrong, absent.

The properties pinned below are each a way that could silently regress:
  * an unpriced model must report *nothing*, never 0
  * both spellings of a model name must resolve to one price
  * a typo in the config must not take the app down
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jc.llm.call_log import cost_micro_usd
from jc.llm.pricing import ModelPrice, parse_pricing, price_for

# --- the price table -------------------------------------------------------------


def test_prices_are_quoted_per_million_tokens() -> None:
    price = ModelPrice(prompt_usd_per_1m=2.5, completion_usd_per_1m=10.0)
    # 1M prompt + 1M completion = $12.50 = 12_500_000 micro-USD.
    assert price.micro_usd(prompt_tokens=1_000_000, completion_tokens=1_000_000) == 12_500_000
    # A realistic turn: 20k prompt, 800 completion.
    assert price.micro_usd(prompt_tokens=20_000, completion_tokens=800) == 58_000


def test_no_usage_is_unpriced_not_free() -> None:
    """Streamed calls carry no token counts at log time. Reporting those as 0 would
    understate spend by however much of the traffic streams."""
    price = ModelPrice(prompt_usd_per_1m=2.5, completion_usd_per_1m=10.0)
    assert price.micro_usd(prompt_tokens=None, completion_tokens=None) is None
    # A half-populated usage block is still priceable.
    assert price.micro_usd(prompt_tokens=1_000_000, completion_tokens=None) == 2_500_000


def test_both_spellings_of_a_model_name_resolve() -> None:
    """`routing.yaml` writes `openai/gpt-6-1-sol` because litellm needs the prefix to
    pick an adapter, but the gateway echoes back the bare name, and that is what gets
    logged as `final_model`. A price configured under one spelling has to match both."""
    table = parse_pricing(
        {"openai/gpt-6-1-sol": {"prompt_usd_per_1m": 1.0, "completion_usd_per_1m": 2.0}}
    )
    assert price_for(table, "gpt-6-1-sol") is not None
    assert price_for(table, "openai/gpt-6-1-sol") is not None
    assert price_for(table, "some-other-model") is None
    assert price_for(table, None) is None


@pytest.mark.parametrize(
    "bad",
    [
        {"m": {"prompt_usd_per_1m": 1.0}},  # missing half the pair
        {"m": {"prompt_usd_per_1m": "free", "completion_usd_per_1m": 1.0}},
        {"m": "1.0 / 2.0"},
        {"m": None},
    ],
)
def test_a_malformed_entry_is_skipped_not_fatal(bad: dict[str, object]) -> None:
    """Pricing is reporting metadata. A typo in it must not stop the app serving."""
    assert parse_pricing(bad) == {}


def test_a_missing_pricing_block_is_simply_empty() -> None:
    assert parse_pricing(None) == {}
    assert parse_pricing([]) == {}


# --- wiring into the audit log ---------------------------------------------------


class _Response(dict):
    """Minimal stand-in: `cost_micro_usd` reads `model` and `usage` off the response."""


def _response(model: str, prompt: int, completion: int) -> _Response:
    return _Response(
        model=model,
        usage={
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        },
    )


def test_configured_price_is_used_for_a_model_litellm_does_not_know(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jc.llm import call_log

    table = parse_pricing(
        {"openai/gpt-6-1-sol": {"prompt_usd_per_1m": 2.5, "completion_usd_per_1m": 10.0}}
    )

    class _Router:
        def price_for_model(self, model: str | None) -> object:
            return price_for(table, model)

    monkeypatch.setattr("jc.llm.router.get_llm_router", lambda: _Router())
    assert call_log.cost_micro_usd(_response("gpt-6-1-sol", 20_000, 800)) == 58_000


def test_an_unpriced_model_reports_nothing_rather_than_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty cell means "we do not know what this cost". A 0 would claim it was
    free. A spend report must not blur the two."""

    class _Router:
        def price_for_model(self, model: str | None) -> object:
            return None

    monkeypatch.setattr("jc.llm.router.get_llm_router", lambda: _Router())
    # litellm does not know this name either, so it raises and we fall through.
    assert cost_micro_usd(_response("not-a-real-model-xyz", 100, 10)) is None


def test_routing_yaml_ships_pricing_documented_but_inactive() -> None:
    """The committed rate card is placeholders. Active placeholders would render a
    confident, wrong 花费 column, which is worse than an empty one — so the block
    stays commented in `routing.yaml` and live only in `routing.example.yaml`."""
    import yaml

    from jc.paths import agent_file

    routing = Path(agent_file("llm", "routing.yaml"))
    text = routing.read_text(encoding="utf-8")
    assert "pricing:" in text, "the pricing block should be documented in place"
    assert yaml.safe_load(text).get("pricing") is None, (
        "placeholder prices must not be active in the real routing config"
    )
