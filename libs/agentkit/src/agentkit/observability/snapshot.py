"""A structured snapshot of this process's metrics, for dashboards.

`render_metrics()` produces the Prometheus text format, which is right for a
scraper and awkward for a UI. This module turns the same registry into plain
data a frontend can chart, keeping the vocabulary identical so the two views can
never disagree about what a number means.

Two consumers, one shape:

- **A live dashboard** polls `snapshot()` through its own service's HTTP API.
- **A multi-service dashboard** fetches the same payload from every service it
  knows about and switches between them. That is why the payload names its own
  service and process identity: a chart's legend has to say *which* process the
  line came from, and two workers behind one port are two processes.

Design constraints, inherited from `metrics`:

- Values are floats/ints/strings only — no collector objects — so the result is
  JSON-serializable and safe to hand to a template.
- A missing or broken collector yields a partial snapshot rather than an error.
  A dashboard that renders nine of ten panels beats one that renders none.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Any, Final

from .metrics import (
    MULTIPROCESS_MODE,
    PROMETHEUS_AVAILABLE,
    REGISTRY,
    _state,
    collector_registry,
    metrics_enabled,
)


def _configured_identity(key: str) -> str | None:
    """The name this process was configured with. Read live — `configure` may run later."""
    value = _state.get(key)
    return str(value) if value else None

logger = logging.getLogger(__name__)

#: Metric families this kit owns. Anything else in the registry (Python GC,
#: process memory) is present in the Prometheus text output but belongs to
#: prometheus_client, not to us — a dashboard built on this vocabulary should
#: not start depending on collector internals that upstream may rename.
OWNED_PREFIXES: Final = (
    "llm_",
    "agent_",
    "method_",
)

#: How many distinct series one family may contribute to a snapshot. A runaway
#: label value (a bug, not a design) would otherwise turn a 200 ms dashboard
#: request into a megabyte response. Truncation is reported, never silent.
MAX_SERIES_PER_FAMILY: Final = 400


def _sample_value(sample: Any) -> float | int | None:
    """Prometheus samples carry a float; counters read better as ints."""
    if sample.name.endswith("_total") or sample.name.endswith("_count"):
        try:
            return int(sample.value)
        except (TypeError, ValueError):
            return None
    try:
        return float(sample.value)
    except (TypeError, ValueError):
        return None


def _family_payload(family: Any) -> dict[str, Any] | None:
    """One metric family as {type, help, series:[{labels, value}]}.

    Histograms expand into their bucket/count/sum samples, which is what the
    dashboard needs to draw a percentile panel without re-deriving buckets.
    """
    kind = family.type
    samples = list(family.samples)
    truncated = len(samples) > MAX_SERIES_PER_FAMILY
    if truncated:
        samples = samples[:MAX_SERIES_PER_FAMILY]
    series = []
    for sample in samples:
        labels = dict(getattr(sample, "labels", {}) or {})
        suffix = sample.name
        base = family.name
        # Keep the statistical suffix distinguishable: the bucket line for
        # `agent_phase_duration_seconds` and its `_count` line are different
        # series to a chart, not the same one twice.
        if suffix.startswith(base):
            suffix = suffix[len(base):].lstrip("_") or "value"
        series.append({"suffix": suffix, "labels": labels, "value": _sample_value(sample)})
    return {
        "type": kind,
        "help": family.documentation,
        "series": series,
        "truncated": truncated,
    }


def snapshot(*, service: str | None = None) -> dict[str, Any]:
    """This process's metrics as JSON-ready data.

    ``service`` overrides the label-derived service name for callers that know
    better than the registry (rare); normally the `application` label already
    says it.
    """
    # Identity comes from `configure()`, not from the series labels. Reading it
    # off the labels made a fresh process report `service: None` — the one moment
    # a dashboard most needs to know *whose* empty panel it is showing.
    payload: dict[str, Any] = {
        "service": service or _configured_identity("app"),
        "environment": _configured_identity("env"),
        "enabled": metrics_enabled() and PROMETHEUS_AVAILABLE,
        "captured_at": time.time(),
        # Process identity, not decoration: a service behind `--workers N` is N
        # independent registries, and a dashboard that merged them without saying
        # so would show arithmetic that no single process ever produced. With
        # these two fields a client can keep one line per process.
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "families": {},
        "errors": [],
    }
    if not payload["enabled"] or REGISTRY is None:
        return payload
    # Read the merged view in multiprocess mode; a worker's own registry only
    # ever holds that worker's values.

    try:
        families = list(collector_registry().collect())
    except Exception:  # pragma: no cover - a broken collector must not 500
        logger.warning("metric registry collect failed", exc_info=True)
        payload["errors"].append("registry collect failed")
        return payload

    for family in families:
        if not family.name.startswith(OWNED_PREFIXES):
            continue
        try:
            rendered = _family_payload(family)
        except Exception:  # pragma: no cover
            logger.debug("metric family %s unrenderable", family.name, exc_info=True)
            payload["errors"].append(f"family {family.name} skipped")
            continue
        if rendered is None:
            continue
        payload["families"][family.name] = rendered


    return payload
