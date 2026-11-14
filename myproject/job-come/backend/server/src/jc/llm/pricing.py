"""Pricing moved to `agentkit.llm.pricing`; this module keeps the import path.

Why the move: token-price arithmetic is not JC-specific. Every service that
reports a cost has to convert a gateway's per-million quote into micro-USD and
must not confuse "unpriced" with "free" — the same two decisions, in the same
shape.

Why the shim: `jc.llm.pricing` is imported by the router, the call log and the
tests. Re-pointing those in the same change would bury the move inside unrelated
diffs; a two-line re-export keeps this commit reviewable and costs nothing at
runtime. Delete it once nothing external references the old path.
"""

from __future__ import annotations

from agentkit.llm.pricing import ModelPrice, parse_pricing, price_for

__all__ = ["ModelPrice", "parse_pricing", "price_for"]
