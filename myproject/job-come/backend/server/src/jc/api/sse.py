"""SSE keep-alive: a transport concern, not something `agent_service` should know.

Why this is not inside `AgentService.stream_message`
------------------------------------------------------
A heartbeat answers "is the connection still alive", which only matters once the
business event stream is already wrapped in an HTTP response. Teaching the service
layer to interleave timer ticks with its own events would make every yield point in
`stream_message` double as a liveness probe, for a concern that belongs to the inbound
adapter (`api/`) per ADR-004's layering, not to business orchestration.

Why a heartbeat and not just a bigger client timeout
------------------------------------------------------
`coach`/`writer` resolve through a 3-hop failover chain (`routing.yaml`), each hop
timing out at up to 180s. A client timeout sized to the worst case (3 x 180s) would
leave a genuinely stuck request looking identical to a healthy one for nine minutes.
A client timeout sized to look responsive (120s) fires routinely mid-failover, which
is the bug this closes: the frontend was guessing a duration instead of being told the
connection is still there. A heartbeat turns "no event for 120s" (ambiguous: dead, or
just slow?) into "no event at all, including pings, for N seconds" (unambiguous: dead).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import anyio
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send


class ClosingStreamingResponse(StreamingResponse):
    """Close request-owned iterators on send failure as well as receive disconnect.

    If send() raises while the iterator is suspended at yield, merely unwinding
    StreamingResponse does not synchronously close that iterator. Its producer
    could then outlive request dependencies (including the database session).
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                close = getattr(self.body_iterator, "aclose", None)
                if close is not None:
                    await close()


#: Emitted when no upstream event arrives within this many seconds. Short enough that
#: the client's own "connection looks dead" timeout can be set just past it, long
#: enough that it does not add meaningful overhead to a healthy stream.
HEARTBEAT_INTERVAL_SEC = 15.0

async def with_heartbeat(
    events: AsyncIterator[dict], *, interval_sec: float = HEARTBEAT_INTERVAL_SEC
) -> AsyncIterator[dict]:
    """Interleave `{"type": "ping"}` into `events` whenever it falls silent.

    The underlying iterator is pulled from a background task so a slow upstream event
    (e.g. a model stuck mid-failover) cannot block this generator from yielding its own
    pings in the meantime - that blocking is exactly the situation a heartbeat exists to
    surface.
    """
    source = events.__aiter__()
    pending: asyncio.Task[dict] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(source.__anext__())
            try:
                event = await asyncio.wait_for(asyncio.shield(pending), timeout=interval_sec)
            except TimeoutError:
                yield {"type": "ping"}
                continue
            except StopAsyncIteration:
                return
            pending = None
            yield event
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
