"""Prometheus metrics for agent services: one vocabulary, usable from any layer.

The metrics answer four questions an operator actually asks:

1. **Is it slow, and where?** — a duration histogram per *phase* (agent build,
   model call, tool call, stream), so "16 seconds" resolves into named pieces
   instead of one opaque number.
2. **Is it failing?** — a counter split by status and error type.
3. **How much is it doing?** — QPS from the same counter (`rate(...)` in
   PromQL), plus a token counter for model cost.
4. **Which model/gateway?** — labels carry the served model and the endpoint,
   which is what makes a provider regression visible before users report it.

Design constraints, all deliberate:

- **No label may take unbounded values.** A label holding a user id, session id
  or free-text error message explodes the series count and is the usual reason a
  metrics backend falls over. Everything here is a small closed set: scenario,
  model, phase, status, error class.
- **Recording never raises into the caller.** A metrics failure must not break a
  request; every public function is wrapped.
- **Missing ``prometheus_client`` is not an error.** The package stays importable
  in a bare library context and every function degrades to a no-op.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Final

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised by the no-prometheus test
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
    try:
        from prometheus_client import CollectorRegistry, multiprocess

        MULTIPROCESS_AVAILABLE = True
    except ImportError:  # pragma: no cover
        CollectorRegistry = None  # type: ignore[assignment]
        multiprocess = None  # type: ignore[assignment]
        MULTIPROCESS_AVAILABLE = False
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    class _Missing:
        """Stand-in so module-level metric definitions stay importable."""

        def labels(self, *a: Any, **kw: Any) -> "_Missing":
            return self

        def inc(self, *a: Any, **kw: Any) -> None:
            return None

        def observe(self, *a: Any, **kw: Any) -> None:
            return None

        def set(self, *a: Any, **kw: Any) -> None:
            return None

    Counter = Gauge = Histogram = lambda *a, **kw: _Missing()  # noqa: E731
    REGISTRY = None
    CollectorRegistry = None  # type: ignore[assignment]
    multiprocess = None  # type: ignore[assignment]
    MULTIPROCESS_AVAILABLE = False
    generate_latest = lambda *_a, **_kw: b""  # noqa: E731

CONTENT_TYPE: Final = CONTENT_TYPE_LATEST

_lock = threading.Lock()
_state: dict[str, Any] = {
    "app": "agent",
    "env": "dev",
    "enabled": True,
}

#: Boundaries chosen from measured agent behaviour rather than a generic default:
#: a model call is 3–15 s here, an agent build 4–40 s, and a whole turn 10–60 s.
#: The dense region is 1–30 s because that is where "is this normal?" is decided;
#: 60 s+ exists only so a pathological run still lands in a bucket.
_LATENCY_BUCKETS: Final = (
    0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 10.0,
    15.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 300.0, float("inf"),
)


def configure(*, application: str, environment: str, enabled: bool = True) -> None:
    """Name this service and its environment. Call once at startup.

    The two become labels on every series, which is what lets one Prometheus
    scrape several deployments and still tell them apart.
    """
    with _lock:
        _state["app"] = application
        _state["env"] = environment
        _state["enabled"] = bool(enabled) and PROMETHEUS_AVAILABLE


#: Whether counters are shared across worker processes.
#:
#: Decided at IMPORT time, not by a function call, because prometheus_client
#: fixes its value implementation the moment it is imported
#: (`prometheus_client/values.py`: `ValueClass = get_value_class()`). A
#: `enable_multiprocess(dir)` helper — the first version of this module had one —
#: cannot work: by the time it runs, the class is chosen, the metrics already use
#: in-process floats, and nothing is ever written to disk. It returned True and
#: silently exported per-worker numbers, which is worse than not supporting the
#: feature at all.
#:
#: So the switch is `PROMETHEUS_MULTIPROC_DIR` in the process environment,
#: exported by whatever starts the server, before Python imports this package.
MULTIPROCESS_MODE: Final = bool(
    PROMETHEUS_AVAILABLE and MULTIPROCESS_AVAILABLE
    and __import__("os").environ.get("PROMETHEUS_MULTIPROC_DIR")
)

_collector_registry: Any = None


def _merged_registry() -> Any:
    """A registry that merges every worker's mmap files, built once.

    In multiprocess mode metrics are *created* in the default REGISTRY (that is
    what writes them to the shared directory) and *read* through this merged
    view. Reading the default registry in a worker would only ever show that
    worker's own values.
    """
    global _collector_registry
    if _collector_registry is not None:
        return _collector_registry
    merged = CollectorRegistry()
    multiprocess.MultiProcessCollector(merged)
    _collector_registry = merged
    return merged


def collector_registry() -> Any:
    """The registry to scrape or snapshot: merged in multiprocess mode."""
    return _merged_registry() if MULTIPROCESS_MODE else REGISTRY


def sharing_across_processes() -> bool:
    """Whether counters are aggregated across worker processes.

    False under `--workers N` means every number describes exactly one worker.
    Callers should say so rather than presenting a partial view as the whole.
    """
    return MULTIPROCESS_MODE


def mark_worker_exit() -> None:
    """Tell prometheus_client this pid is gone. Call from a worker's shutdown.

    Without it a dead worker's mmap file stays behind and its counters keep
    contributing to every future sum — totals inflate on each restart and never
    come back down. Cheap, and the alternative is a dashboard that slowly lies.
    """
    if not MULTIPROCESS_MODE:
        return
    try:
        multiprocess.mark_process_dead(__import__("os").getpid())
    except Exception:  # pragma: no cover - cleanup must never block shutdown
        logger.debug("mark_process_dead failed", exc_info=True)


def registry() -> Any:
    """The registry NEW metrics should be created in.

    Always the default registry: in multiprocess mode that is the one backed by
    the shared directory. `collector_registry()` is the different view used for
    reading.
    """
    return REGISTRY


def metrics_enabled() -> bool:
    return bool(_state["enabled"])


def _base() -> dict[str, str]:
    return {"application": str(_state["app"]), "env": str(_state["env"])}


def _metric(factory: Any, name: str, doc: str, labels: tuple[str, ...], **kw: Any) -> Any:
    """Create one metric, tolerating a duplicate registration in the same process.

    Tests and reloads can import this module twice; prometheus_client raises on a
    duplicate name. Returning the already-registered collector keeps that a
    non-event instead of a startup crash.
    """
    target = registry()
    if target is not None:
        kw = {**kw, "registry": target}
    try:
        return factory(name, doc, labels, **kw)
    except ValueError:
        for coll in getattr(target, "_names_to_collectors", {}).values():
            if getattr(coll, "_name", None) == name:
                return coll
        raise


# --------------------------------------------------------------------------
# Metric definitions
# --------------------------------------------------------------------------
# Built lazily, on first use, not at import time.
#
# Lazy rather than module-level for two reasons:
#
# 1. `import agentkit.observability` must not create collectors in whatever
#    registry happens to be current. A library that registers metrics on import
#    cannot be imported twice (tests, reloads) without a duplicate-name error.
# 2. It keeps the one decision that must happen earlier — whether counters are
#    shared across worker processes — from being silently pre-empted. That
#    decision is prometheus_client's, taken at ITS import time, and is read here
#    as `MULTIPROCESS_MODE`. Creating metrics eagerly would not change it, but it
#    would make the failure harder to see: see the note on `MULTIPROCESS_MODE`
#    for the bug this replaced.
#
# Cost of the indirection: one dict lookup per recorded observation.

_DEFINITIONS: dict[str, tuple[Any, str, str, tuple[str, ...], dict[str, Any]]] = {
    "LLM_LATENCY": (
        Histogram, "llm_call_duration_seconds",
        "One model call, end to end (includes gateway queueing).",
        ("application", "env", "scenario", "model", "status"),
        {"buckets": _LATENCY_BUCKETS},
    ),
    "LLM_CALLS": (
        Counter, "llm_calls_total",
        "Model calls by scenario, served model and outcome.",
        ("application", "env", "scenario", "model", "status", "error_type"),
        {},
    ),
    "LLM_TOKENS": (
        Counter, "llm_tokens_total",
        "Tokens consumed, split by direction.",
        ("application", "env", "scenario", "model", "direction"),
        {},
    ),
    "LLM_ATTEMPTS": (
        Histogram, "llm_attempts_per_call",
        "How many endpoints one logical call needed; >1 means failover kicked in.",
        ("application", "env", "scenario"),
        {"buckets": (1.0, 2.0, 3.0, 4.0, 5.0, float("inf"))},
    ),
    "AGENT_PHASE": (
        Histogram, "agent_phase_duration_seconds",
        "Named phase inside an agent turn (build / model / tool / stream).",
        ("application", "env", "phase", "outcome"),
        {"buckets": _LATENCY_BUCKETS},
    ),
    "AGENT_TURNS": (
        Counter, "agent_turns_total",
        "Agent turns started, by role and outcome.",
        ("application", "env", "role", "status"),
        {},
    ),
    "METHOD_LATENCY": (
        Histogram, "method_duration_seconds",
        "Any decorated method's duration; `target` is Class.method.",
        ("application", "env", "target", "status"),
        {"buckets": _LATENCY_BUCKETS},
    ),
    "METHOD_CALLS": (
        Counter, "method_calls_total",
        "Any decorated method's call count and outcome.",
        ("application", "env", "target", "status", "error_type"),
        {},
    ),
    "INFLIGHT": (
        Gauge, "agent_turns_in_flight",
        "Turns currently running; a number that only grows means something is stuck.",
        ("application", "env"),
        {},
    ),
}

_built: dict[str, Any] = {}


class _NoopMetric:
    """Stands in for a metric when prometheus_client is not installed.

    Returning this instead of raising keeps the "library stays importable"
    promise: a caller's `record_*` still runs, observes nothing, and costs one
    attribute read.
    """

    def labels(self, *a: Any, **kw: Any) -> "_NoopMetric":
        return self

    def inc(self, *a: Any, **kw: Any) -> None:
        return None

    def dec(self, *a: Any, **kw: Any) -> None:
        return None

    def observe(self, *a: Any, **kw: Any) -> None:
        return None

    def set(self, *a: Any, **kw: Any) -> None:
        return None


_NOOP_METRIC = _NoopMetric()


def _get(name: str) -> Any:
    """The metric for `name`, built on first use in the active registry."""
    existing = _built.get(name)
    if existing is not None:
        return existing
    if not PROMETHEUS_AVAILABLE:
        return _NOOP_METRIC
    factory, metric_name, doc, labels, kw = _DEFINITIONS[name]
    metric = _metric(factory, metric_name, doc, labels, **kw)
    _built[name] = metric
    return metric


def _reset_metrics() -> None:
    """Drop built metrics so a new registry takes effect. Tests and reconfigure."""
    _built.clear()


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


def record_llm_metrics(
    *,
    scenario: str,
    model: str | None,
    duration: float | None = None,
    status: str = "success",
    error_type: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    attempts: int | None = None,
) -> None:
    """One logical model call, after it finished or failed.

    ``status``/``error_type`` are the only place failure detail enters a metric,
    and both are short closed sets — never an exception message, which would be
    unbounded and can contain user data.
    """
    if not metrics_enabled():
        return
    try:
        labels = {**_base(), "scenario": scenario or "unknown",
                  "model": model or "unknown"}
        if duration is not None:
            _get("LLM_LATENCY").labels(**labels, status=status).observe(duration)
        _get("LLM_CALLS").labels(**labels, status=status,
                         error_type=(error_type or "")[:48]).inc()
        if prompt_tokens:
            _get("LLM_TOKENS").labels(**labels, direction="input").inc(prompt_tokens)
        if completion_tokens:
            _get("LLM_TOKENS").labels(**labels, direction="output").inc(completion_tokens)
        if attempts is not None:
            _get("LLM_ATTEMPTS").labels(**_base(), scenario=scenario or "unknown").observe(attempts)
    except Exception:  # pragma: no cover - metrics must never break a request
        logger.debug("record_llm_metrics failed", exc_info=True)


def record_agent_phase(*, phase: str, duration: float, outcome: str = "ok") -> None:
    """One named phase of a turn. Phases are the unit that makes a slow turn legible.

    Called from the turn loop with e.g. ``build`` (graph construction), ``ttft``
    (send → first token), ``generate`` (first token → done), ``tool``.
    """
    if not metrics_enabled():
        return
    try:
        _get("AGENT_PHASE").labels(**_base(), phase=phase, outcome=outcome).observe(duration)
    except Exception:  # pragma: no cover
        logger.debug("record_agent_phase failed", exc_info=True)


def record_agent_turn(*, role: str, status: str = "success") -> None:
    if not metrics_enabled():
        return
    try:
        _get("AGENT_TURNS").labels(**_base(), role=role or "unknown", status=status).inc()
    except Exception:  # pragma: no cover
        logger.debug("record_agent_turn failed", exc_info=True)


def record_method(*, target: str, duration: float, status: str, error_type: str | None = None) -> None:
    if not metrics_enabled():
        return
    try:
        _get("METHOD_LATENCY").labels(**_base(), target=target, status=status).observe(duration)
        _get("METHOD_CALLS").labels(**_base(), target=target, status=status,
                            error_type=(error_type or "")[:48]).inc()
    except Exception:  # pragma: no cover
        logger.debug("record_method failed", exc_info=True)


class _Inflight:
    """Track concurrent turns so a leak shows up as a gauge that only rises."""

    def __enter__(self) -> "_Inflight":
        if metrics_enabled():
            try:
                _get("INFLIGHT").labels(**_base()).inc()
            except Exception:  # pragma: no cover
                pass
        return self

    def __exit__(self, *exc: Any) -> None:
        if metrics_enabled():
            try:
                _get("INFLIGHT").labels(**_base()).dec()
            except Exception:  # pragma: no cover
                pass


def inflight_turn() -> _Inflight:
    return _Inflight()


# Thin factories, kept only so a caller can add its own metric with the same
# conventions (base labels, same registry) instead of re-deriving them.
def counter(name: str, doc: str, labels: tuple[str, ...]) -> Any:
    return _metric(Counter, name, doc, (*labels, "application", "env"))


def gauge(name: str, doc: str, labels: tuple[str, ...]) -> Any:
    return _metric(Gauge, name, doc, (*labels, "application", "env"))


def histogram(name: str, doc: str, labels: tuple[str, ...]) -> Any:
    return _metric(Histogram, name, doc, (*labels, "application", "env"),
                   buckets=_LATENCY_BUCKETS)


def render_metrics() -> bytes:
    """The scrape payload. Empty (not an error) when metrics are off."""
    if not PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n"
    try:
        return generate_latest(collector_registry())
    except Exception:  # pragma: no cover
        logger.warning("render_metrics failed", exc_info=True)
        return b"# metrics unavailable\n"
