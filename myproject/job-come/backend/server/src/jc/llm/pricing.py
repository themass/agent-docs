"""Per-token prices for models litellm does not know about.

Why this file exists
--------------------
`cost_micro_usd` asks `litellm.completion_cost`, which looks the served model up in
litellm's bundled price map. Every model in `routing.yaml` is reached through a
gateway under a vendor-neutral name (`gpt-6-1-sol`, `deepseek-v4-flash`,
`claude-haiku-5-5`, `qwen-vl-ocr`), and none of those names are in that map — so
`completion_cost` raises, the helper returns `None`, and the admin LLM list showed an
empty 花费 column for every single row. The number was never wrong; it was absent.

A gateway's prices are a deployment fact, not a property of the model name, so they
belong in configuration rather than in code. `routing.yaml` is where a model is named
exactly once, which makes it the right place to say what that name costs:

    pricing:
      openai/gpt-6-1-sol:
        prompt_usd_per_1m: 2.5
        completion_usd_per_1m: 10.0

Anything absent from `pricing` still falls through to litellm, so public models keep
working without being listed, and an unpriced model keeps reporting `None` (an empty
cell) rather than a fabricated 0 — "we do not know" and "it was free" must not look
the same in a cost report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: USD per one million tokens -> micro-USD per token is a factor of 1e6/1e6 == 1,
#: which is why prices are quoted per 1M: the conversion is exact in integers and a
#: per-token float price would be a rounding trap at these magnitudes.
_PER_MILLION = 1_000_000


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Prices in USD per 1M tokens, as quoted by gateways and vendors."""

    prompt_usd_per_1m: float
    completion_usd_per_1m: float

    def micro_usd(self, *, prompt_tokens: int | None, completion_tokens: int | None) -> int | None:
        """Cost in micro-USD, or `None` when there are no token counts to price.

        `None` rather than 0 for a missing usage block: streamed calls legitimately
        have no token counts at log time, and reporting those as free would quietly
        understate spend by however much of the traffic is streamed.
        """
        if prompt_tokens is None and completion_tokens is None:
            return None
        prompt = (prompt_tokens or 0) * self.prompt_usd_per_1m
        completion = (completion_tokens or 0) * self.completion_usd_per_1m
        return int(round((prompt + completion) / _PER_MILLION * 1_000_000))


def parse_pricing(raw: object) -> dict[str, ModelPrice]:
    """Build the price table from the `pricing:` block of `routing.yaml`.

    A malformed entry is skipped with a warning rather than raising: pricing is
    reporting metadata, and a typo in it must not stop the app from serving traffic.
    """
    if not isinstance(raw, dict):
        return {}
    table: dict[str, ModelPrice] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            logger.warning("ignoring malformed pricing entry for %s", name)
            continue
        try:
            table[_normalise(str(name))] = ModelPrice(
                prompt_usd_per_1m=float(spec["prompt_usd_per_1m"]),
                completion_usd_per_1m=float(spec["completion_usd_per_1m"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("ignoring malformed pricing entry for %s", name)
    return table


def _normalise(model: str) -> str:
    """Strip the litellm provider prefix so both spellings resolve to one entry.

    `routing.yaml` names models as `openai/gpt-6-1-sol` (litellm needs the prefix to
    pick an adapter), but what the gateway echoes back in the response — which is what
    gets logged as `final_model` — is the bare `gpt-6-1-sol`. Without this, a price
    configured under one spelling would silently never match the other.
    """
    name = model.strip()
    return name.split("/", 1)[1] if "/" in name else name


def price_for(table: dict[str, ModelPrice], model: str | None) -> ModelPrice | None:
    if not model:
        return None
    return table.get(_normalise(model))
