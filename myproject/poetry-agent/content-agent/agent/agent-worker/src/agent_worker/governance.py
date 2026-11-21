"""Run governance: budgets, retry/backoff, circuit breaker, cancellation (contract sections 6.8, 12).

Everything time-related goes through ``Clock`` so tests run instantly. A ``RuntimeFailure`` is a run
that cannot produce output (D4: DeerFlow failures are FAILED, never silently replaced by the STUB);
``RunCancelled`` is the editor stopping the run and must produce no further writes.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, TypeVar

import yaml

T = TypeVar("T")

# ------------------------------------------------------------------------------------------------
# errors
# ------------------------------------------------------------------------------------------------


class RuntimeFailure(Exception):
    """The run cannot continue. ``reason`` is a short code, safe to put in an event."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class RunCancelled(Exception):
    pass


class UpstreamError(Exception):
    """A failed call to the control bridge or the DeerFlow gateway. Never carries a response body."""

    def __init__(self, target: str, reason: str, *, retryable: bool, status: int | None = None) -> None:
        super().__init__(f"{target}:{reason}")
        self.target = target
        self.reason = reason
        self.retryable = retryable
        self.status = status


# ------------------------------------------------------------------------------------------------
# time and cancellation
# ------------------------------------------------------------------------------------------------


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()
        self.reason = ""

    def cancel(self, reason: str = "cancelled") -> None:
        if not self._event.is_set():
            self.reason = reason
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> bool:
        return self._event.wait(max(0.0, seconds))

    def check(self) -> None:
        if self._event.is_set():
            raise RunCancelled()


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float, cancel: CancelToken | None = None) -> None:
        if cancel is not None:
            cancel.wait(seconds)
        else:
            time.sleep(max(0.0, seconds))


class FakeClock:
    """Deterministic clock for tests: ``sleep`` advances time and returns immediately."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float, cancel: CancelToken | None = None) -> None:
        self.sleeps.append(seconds)
        self.t += max(0.0, seconds)


# ------------------------------------------------------------------------------------------------
# budgets
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Budgets:
    max_turns: int = 12
    max_subagents: int = 0
    max_tool_calls: int = 16
    max_wall_seconds: int = 600
    max_output_chars: int = 40000
    max_tokens: int = 120000
    retry_attempts: int = 3
    backoff_seconds: tuple[float, ...] = (2.0, 5.0, 15.0)
    failure_threshold: int = 3
    open_seconds: float = 120.0
    defaulted: tuple[str, ...] = ()

    def as_event(self) -> dict[str, Any]:
        return {
            "max_tool_calls": self.max_tool_calls, "max_wall_s": self.max_wall_seconds,
            "max_tokens": self.max_tokens, "max_output_chars": self.max_output_chars,
        }


_BOUNDS = {
    "max_turns": (1, 100), "max_subagents": (0, 8), "max_tool_calls": (1, 200),
    "max_wall_seconds": (5, 7200), "max_output_chars": (1000, 500000), "max_tokens": (1000, 2_000_000),
}


def _clamped(raw: dict[str, Any], key: str, default: int, defaulted: list[str]) -> int:
    value = raw.get(key)
    low, high = _BOUNDS[key]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        defaulted.append(key)
        return default
    return value


def load_budgets(path: Path | None, task_type: str) -> Budgets:
    """Read ``budgets.yaml`` (version 2, ``profiles.authoring``). Anything missing/invalid -> safe default."""
    base = Budgets()
    defaulted: list[str] = []
    raw: dict[str, Any] = {}
    if path is None or not path.is_file():
        return replace(base, defaulted=("file",))
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        profile = doc["profiles"]["authoring"]
        raw = dict(profile) if isinstance(profile, dict) else {}
        override = (raw.get("per_task_type") or {}).get(task_type) or {}
        if isinstance(override, dict):
            raw.update(override)
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        return replace(base, defaulted=("file",))
    fields = {k: _clamped(raw, k, getattr(base, k), defaulted) for k in _BOUNDS}
    retry = raw.get("retry") if isinstance(raw.get("retry"), dict) else {}
    attempts = retry.get("max_attempts")
    if isinstance(attempts, int) and not isinstance(attempts, bool) and 1 <= attempts <= 6:
        fields["retry_attempts"] = attempts
    else:
        defaulted.append("retry.max_attempts")
    backoff = retry.get("backoff_seconds")
    if isinstance(backoff, list) and backoff and all(isinstance(x, (int, float)) and 0 <= x <= 300 for x in backoff):
        fields["backoff_seconds"] = tuple(float(x) for x in backoff)
    else:
        defaulted.append("retry.backoff_seconds")
    breaker = raw.get("circuit_breaker") if isinstance(raw.get("circuit_breaker"), dict) else {}
    threshold, opened = breaker.get("failure_threshold"), breaker.get("open_seconds")
    if isinstance(threshold, int) and not isinstance(threshold, bool) and 1 <= threshold <= 20:
        fields["failure_threshold"] = threshold
    else:
        defaulted.append("circuit_breaker.failure_threshold")
    if isinstance(opened, (int, float)) and not isinstance(opened, bool) and 1 <= opened <= 3600:
        fields["open_seconds"] = float(opened)
    else:
        defaulted.append("circuit_breaker.open_seconds")
    return replace(base, defaulted=tuple(defaulted), **fields)


@dataclass
class BudgetTracker:
    budgets: Budgets
    clock: Any = field(default_factory=SystemClock)
    tool_calls: int = 0
    tokens: int = 0
    started: float = 0.0

    def __post_init__(self) -> None:
        self.started = self.clock.now()

    @property
    def elapsed(self) -> float:
        return self.clock.now() - self.started

    def add_tool_call(self, n: int = 1) -> None:
        self.tool_calls += n

    def add_tokens(self, n: int) -> None:
        self.tokens += max(0, n)

    def exceeded(self) -> str | None:
        """Reason code of the first exhausted budget, or ``None``."""
        if self.elapsed > self.budgets.max_wall_seconds:
            return "WALL_TIMEOUT"
        if self.tool_calls > self.budgets.max_tool_calls:
            return "TOOL_BUDGET_EXCEEDED"
        if self.tokens > self.budgets.max_tokens:
            return "TOKEN_BUDGET_EXCEEDED"
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "tool_calls": self.tool_calls, "max_tool_calls": self.budgets.max_tool_calls,
            "elapsed_s": int(self.elapsed), "max_wall_s": self.budgets.max_wall_seconds,
            "tokens": self.tokens, "max_tokens": self.budgets.max_tokens,
        }


# ------------------------------------------------------------------------------------------------
# circuit breaker and retry
# ------------------------------------------------------------------------------------------------


class CircuitBreaker:
    """Opens after ``failure_threshold`` consecutive failed calls; half-opens after ``open_seconds``."""

    def __init__(self, failure_threshold: int, open_seconds: float, clock: Any = None) -> None:
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self.clock = clock or SystemClock()
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    def configure(self, failure_threshold: int, open_seconds: float) -> None:
        with self._lock:
            self.failure_threshold, self.open_seconds = failure_threshold, open_seconds

    @property
    def state(self) -> str:
        with self._lock:
            if self._opened_at is None:
                return "closed"
            return "open" if self.clock.now() - self._opened_at < self.open_seconds else "half_open"

    def reopens_in(self) -> int:
        with self._lock:
            if self._opened_at is None:
                return 0
            return max(0, int(self.open_seconds - (self.clock.now() - self._opened_at)))

    def allow(self) -> bool:
        return self.state != "open"

    def success(self) -> None:
        with self._lock:
            self._failures, self._opened_at = 0, None

    def failure(self) -> bool:
        """Record a failed call. Returns True if the breaker is now open."""
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = self.clock.now()
            return self._opened_at is not None


def call_with_retry[T](
    fn: Callable[[], T],
    *,
    target: str,
    budgets: Budgets,
    breaker: CircuitBreaker | None = None,
    clock: Any = None,
    cancel: CancelToken | None = None,
    on_retry: Callable[[int, str], None] | None = None,
    on_circuit_open: Callable[[int], None] | None = None,
) -> T:
    """Run ``fn`` with bounded retries. Non-retryable errors surface at once; the breaker counts only
    calls whose retries were exhausted (or hit a retryable fault) so a 4xx never trips it."""
    clock = clock or SystemClock()
    attempt = 0
    while True:
        attempt += 1
        if cancel is not None:
            cancel.check()
        if breaker is not None and not breaker.allow():
            if on_circuit_open:
                on_circuit_open(breaker.reopens_in())
            raise RuntimeFailure("CIRCUIT_OPEN", target)
        try:
            result = fn()
        except UpstreamError as exc:
            if not exc.retryable:
                raise
            opened = breaker.failure() if breaker is not None else False
            if opened:
                if on_circuit_open and breaker is not None:
                    on_circuit_open(breaker.reopens_in())
                raise RuntimeFailure("CIRCUIT_OPEN", target) from exc
            if attempt >= budgets.retry_attempts:
                raise RuntimeFailure("RETRIES_EXHAUSTED", f"{target}:{exc.reason}") from exc
            if on_retry:
                on_retry(attempt + 1, exc.reason)
            delay = budgets.backoff_seconds[min(attempt - 1, len(budgets.backoff_seconds) - 1)]
            clock.sleep(delay, cancel)
            continue
        if breaker is not None:
            breaker.success()
        return result
