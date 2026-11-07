"""A run that stops producing events is ended, and the heartbeat does not keep it alive.

The heartbeat only says the server is up. Before this, a hung run kept its connection open with
pings and the user saw "thinking" for as long as the process lived.
"""

from __future__ import annotations

import asyncio

import pytest

from jc.api.sse import with_heartbeat, with_silence_limit


async def _events(*items, then_hang: bool = False):
    for item in items:
        yield item
    if then_hang:
        await asyncio.sleep(3600)


async def _collect(stream):
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_a_finished_run_passes_through_untouched():
    source = _events({"type": "token"}, {"type": "done"})
    out = await _collect(with_silence_limit(source, limit_sec=1))
    assert out == [{"type": "token"}, {"type": "done"}]


@pytest.mark.asyncio
async def test_a_run_silent_past_the_limit_ends_with_an_error_not_a_hang():
    source = _events({"type": "token"}, then_hang=True)
    out = await _collect(with_silence_limit(source, limit_sec=0.2))
    assert out[0] == {"type": "token"}
    assert out[-1]["type"] == "error" and "没有回复" in out[-1]["message"]


@pytest.mark.asyncio
async def test_pings_from_the_heartbeat_do_not_keep_a_hung_run_alive():
    # The heartbeat sits above the limit, exactly as in the agent route. Pings flow for the whole
    # silence, yet the run still ends with an error.
    stream = with_heartbeat(
        with_silence_limit(_events({"type": "token"}, then_hang=True), limit_sec=0.4),
        interval_sec=0.05,
    )
    out = await asyncio.wait_for(_collect(stream), timeout=5)
    pings = [e for e in out if e["type"] == "ping"]
    assert len(pings) >= 3, "the heartbeat should have been pinging during the silence"
    assert out[-1]["type"] == "error"


@pytest.mark.asyncio
async def test_a_slow_but_real_event_within_the_limit_is_not_cut_off():
    async def slow():
        await asyncio.sleep(0.15)
        yield {"type": "token"}
        yield {"type": "done"}

    out = await _collect(with_silence_limit(slow(), limit_sec=0.5))
    assert out == [{"type": "token"}, {"type": "done"}]
