"""Reusable observability kit: Prometheus metrics, method timing, LLM instrumentation.

Copy this package into another agent service and call :func:`configure` once at
startup; everything else is optional.

Why one package rather than calls sprinkled through an app: the operational
question is "where did these 16 seconds go", and answering it requires the same
vocabulary — metric names, label sets, bucket boundaries — at every layer. One
module owning that vocabulary is what makes a slow turn legible instead of a pile
of timings that cannot be compared.

Nothing here is required for the app to work. Every entry point is a no-op when
``prometheus_client`` is absent or metrics are disabled, so importing this in a
library context never introduces a hard dependency.
"""

from __future__ import annotations

from .decorators import method_metrics
from .federation import MetricsPeer, collect as collect_peer_snapshots, parse_peers
from .snapshot import OWNED_PREFIXES, snapshot
from .metrics import (
    CONTENT_TYPE,
    MULTIPROCESS_MODE,
    collector_registry,
    configure,
    counter,
    mark_worker_exit,
    registry as active_registry,
    sharing_across_processes,
    gauge,
    histogram,
    inflight_turn,
    metrics_enabled,
    record_agent_phase,
    record_agent_turn,
    record_llm_metrics,
    record_method,
    render_metrics,
)

__all__ = [
    "CONTENT_TYPE",
    "configure",
    "counter",
    "gauge",
    "histogram",
    "inflight_turn",
    "method_metrics",
    "metrics_enabled",
    "record_agent_phase",
    "record_agent_turn",
    "record_llm_metrics",
    "record_method",
    "render_metrics",
    "snapshot",
    "MetricsPeer",
    "collect_peer_snapshots",
    "parse_peers",
    "OWNED_PREFIXES",
    "MULTIPROCESS_MODE",
    "collector_registry",
    "mark_worker_exit",
]
