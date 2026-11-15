"""The repair budget must not be smaller than what a repair actually costs.

Production evidence: 4 of 8 repairs ended in `Preview repair unavailable;
keeping first draft: TimeoutError` — never a rejection. The repair reuses the
full writer prompt (~14k input tokens by design), so a 40 s budget sat below the
writer's own per-hop time and could only ever time out.

The failure was invisible because the code degrades gracefully: the user got the
first draft and the repair feature simply never appeared to fire. So the guard
here is on the relationship between the budgets, not on an observed duration —
a timing test would need a real gateway to fail.
"""

from __future__ import annotations

from jc.config import settings

#: The SSE budget the whole preview must fit in, and the browser watchdog after it.
SSE_BUDGET_SECONDS = 240


def test_a_preview_repair_is_allowed_at_least_as_long_as_the_writer_hop():
    """A repair sends more input than the first pass, so it cannot be cheaper."""
    # The writer budget is a whole-chain budget shared by its hops; with the
    # shipped two-hop chain this is the per-hop allowance.
    writer_hop = settings.jc_preview_writer_timeout_seconds / 2
    assert settings.jc_preview_repair_timeout_seconds >= writer_hop, (
        "the repair pass reuses the full writer prompt, so giving it less time "
        "than one writer hop guarantees a timeout rather than a repair"
    )


def test_writer_plus_repair_still_fits_the_stream_budget():
    total = (
        settings.jc_preview_writer_timeout_seconds
        + settings.jc_preview_repair_timeout_seconds
    )
    assert total < SSE_BUDGET_SECONDS, (
        f"writer {settings.jc_preview_writer_timeout_seconds}s + repair "
        f"{settings.jc_preview_repair_timeout_seconds}s = {total}s leaves no room "
        f"for extraction, persistence and streaming inside {SSE_BUDGET_SECONDS}s"
    )
