"""Admin metrics dashboard schemas.

Deliberately loose where the data is opaque to this service: a peer's metric
families come from whatever version of `agentkit.observability` that peer runs,
so pinning them here would make the panel refuse to render a newer service. The
fields that matter for correctness — who answered, whether it answered, how long
it took — are typed strictly.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MetricsPeerStatus(BaseModel):
    """One service's row in the panel, whether or not it answered."""

    name: str
    url: str | None = None
    #: False means the fetch failed. The panel shows this row in a failure state
    #: rather than dropping it: a missing service reads as a healthy platform.
    ok: bool
    latency_ms: int = 0
    #: Error class name only — never a message, which can echo a URL.
    error: str | None = None
    service: str | None = None
    environment: str | None = None
    captured_at: float | None = None
    families: dict[str, Any] = Field(default_factory=dict)


class AdminMetricsSnapshotResponse(BaseModel):
    """All services' snapshots for one dashboard load."""

    peers: list[MetricsPeerStatus]
    #: Whether this service's own counters are shared across worker processes.
    #: False under `--workers N` means every number below describes exactly one
    #: worker, and the panel labels it that way.
    sharing_across_processes: bool = False
    #: Peers configured but unreachable still appear in `peers` with ok=false;
    #: this count is here so a caller can alert without scanning the list.
    unavailable: int = 0
