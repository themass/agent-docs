"""`with_heartbeat` turns upstream silence into an explicit signal.

The bug this guards against: a client-side timeout sized for a healthy stream
(120s) firing routinely mid-failover (`coach`/`writer` can legitimately take
up to 3 x 180s), because "no event in 120s" was the client's only signal and
it cannot tell a slow-but-alive connection from a dead one.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from jc.api.sse import with_heartbeat


async def _events(items: list[dict], delays: list[float]) -> AsyncIterator[dict]:
    for item, delay in zip(items, delays, strict=True):
        if delay:
            await asyncio.sleep(delay)
        yield item


@pytest.mark.asyncio
async def test_fast_stream_passes_through_with_no_pings() -> None:
    events = _events([{"type": "token", "content": "a"}, {"type": "done"}], [0, 0])
    seen = [e async for e in with_heartbeat(events, interval_sec=1.0)]
    assert seen == [{"type": "token", "content": "a"}, {"type": "done"}]


@pytest.mark.asyncio
async def test_slow_upstream_yields_pings_before_the_real_event() -> None:
    # The upstream event takes 0.25s to arrive; a 0.1s heartbeat interval must
    # surface at least one ping before it does, instead of blocking silently.
    events = _events([{"type": "token", "content": "a"}], [0.25])
    seen = [e async for e in with_heartbeat(events, interval_sec=0.1)]
    assert seen[-1] == {"type": "token", "content": "a"}
    assert sum(1 for e in seen if e["type"] == "ping") >= 1


@pytest.mark.asyncio
async def test_pings_stop_once_the_stream_ends() -> None:
    events = _events([{"type": "done"}], [0])
    seen = [e async for e in with_heartbeat(events, interval_sec=0.05)]
    assert seen == [{"type": "done"}]
