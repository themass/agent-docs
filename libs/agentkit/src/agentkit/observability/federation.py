"""Federate metrics from several services into one dashboard payload.

One process's `/metrics/snapshot` answers "how is *this* service doing". An
operator's actual question is "how is *the platform* doing", which spans services
this code has no compile-time knowledge of. This module is the client half: given
a list of `name=url` peers, fetch each one's snapshot and return them together.

Design decisions worth stating, because each one prevents a specific kind of
dashboard that lies:

- **A peer that is down is reported as down, not omitted.** A missing service looks
  like a healthy platform. Each peer returns a row whether it answered or not, so
  an empty chart means "no data yet" and a red row means "we could not ask".
- **Failures are per-peer and time-bounded.** One hanging peer must not hold the
  panel for thirty seconds; the timeout is short and the rest still render.
- **Nothing is re-aggregated here.** The panel receives each service's own
  numbers. Summing counters across services would invent a number no service ever
  produced (and double-count if a peer is listed twice), so that stays the
  consumer's decision, made visibly.
- **The peer list is configuration, not discovery.** Deliberate: a service that
  can reach arbitrary URLs reported in config is a server-side request forgery
  machine. Callers pass a fixed list; this module never derives one from a
  request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Long enough for a busy service, short enough that a dead one does not define
#: how long the panel takes to load.
PEER_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class MetricsPeer:
    name: str
    url: str

    @property
    def snapshot_url(self) -> str:
        return f"{self.url.rstrip('/')}/metrics/snapshot"


def parse_peers(raw: str) -> list[MetricsPeer]:
    """`a=http://x,b=http://y` → peers. Malformed entries are skipped and logged.

    Skipping rather than raising is deliberate: one typo in a deployment's env var
    should cost that one peer, not the whole dashboard.
    """
    peers: list[MetricsPeer] = []
    seen: set[str] = set()
    for chunk in (raw or "").split(","):
        entry = chunk.strip()
        if not entry:
            continue
        name, sep, url = entry.partition("=")
        name, url = name.strip(), url.strip()
        if not sep or not name or not url:
            logger.warning("ignoring malformed JC_METRICS_PEERS entry: %r", entry)
            continue
        if not url.startswith(("http://", "https://")):
            logger.warning("ignoring metrics peer %s: url must be http(s)", name)
            continue
        if name in seen:
            logger.warning("ignoring duplicate metrics peer name: %s", name)
            continue
        seen.add(name)
        peers.append(MetricsPeer(name=name, url=url))
    return peers


async def _fetch_one(client: httpx.AsyncClient, peer: MetricsPeer) -> dict[str, Any]:
    """One peer's snapshot, always as a row — success or failure."""
    started = time.perf_counter()
    try:
        response = await client.get(peer.snapshot_url)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response.raise_for_status()
        payload = response.json()
        return {
            "name": peer.name,
            "url": peer.url,
            "ok": True,
            "latency_ms": elapsed_ms,
            "snapshot": payload,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - one peer must not break the panel
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("metrics peer %s unavailable: %s", peer.name, exc)
        return {
            "name": peer.name,
            "url": peer.url,
            "ok": False,
            "latency_ms": elapsed_ms,
            "snapshot": None,
            # Class name, not the message: a URL echoed back in an error can carry
            # credentials, and this payload is rendered in a browser.
            "error": type(exc).__name__,
        }


async def collect(
    peers: list[MetricsPeer], *, local: dict[str, Any] | None = None, local_name: str = "self"
) -> list[dict[str, Any]]:
    """Every peer's snapshot plus this service's own, fetched concurrently.

    `local` lets the caller pass its own snapshot directly instead of making the
    panel HTTP to itself — one fewer hop, and it cannot fail for reasons the
    caller's own request did not already hit.
    """
    rows: list[dict[str, Any]] = []
    if local is not None:
        rows.append({
            "name": local_name,
            "url": None,
            "ok": True,
            "latency_ms": 0,
            "snapshot": local,
            "error": None,
        })

    if peers:
        async with httpx.AsyncClient(timeout=PEER_TIMEOUT_SECONDS) as client:
            rows.extend(await asyncio.gather(*(_fetch_one(client, p) for p in peers)))
    return rows
