"""Budgets, retry/backoff, circuit breaker, cancellation (contract sections 6.8, 12)."""
from __future__ import annotations

from pathlib import Path

import pytest
from agent_worker.governance import (
    Budgets,
    BudgetTracker,
    CancelToken,
    CircuitBreaker,
    FakeClock,
    RunCancelled,
    RuntimeFailure,
    UpstreamError,
    call_with_retry,
    load_budgets,
)

PROFILE = Path(__file__).resolve().parents[2] / "deerflow-profile" / "config" / "budgets.yaml"


def err(retryable: bool = True, reason: str = "HTTP_503") -> UpstreamError:
    return UpstreamError("deerflow", reason, retryable=retryable)


# ---- budgets.yaml ---------------------------------------------------------------------------------
def test_the_real_profile_budgets_load_without_defaults() -> None:
    gap = load_budgets(PROFILE, "GAP_ANALYSIS")
    assert gap.defaulted == () and gap.max_wall_seconds == 300          # per_task_type overrides the top level
    assert (gap.max_tool_calls, gap.max_output_chars, gap.max_tokens, gap.max_turns) == (24, 60000, 200000, 18)
    assert gap.retry_attempts == 3 and gap.backoff_seconds == (2.0, 5.0, 15.0)
    assert (gap.failure_threshold, gap.open_seconds) == (3, 120.0)
    assert load_budgets(PROFILE, "SCRIPT_DRAFT").max_wall_seconds == 900


def test_missing_or_broken_files_fall_back_to_conservative_defaults(tmp_path: Path) -> None:
    default = Budgets()
    assert load_budgets(None, "GAP_ANALYSIS").defaulted == ("file",)
    assert load_budgets(tmp_path / "absent.yaml", "GAP_ANALYSIS").max_tool_calls == default.max_tool_calls
    for text in ("::: not yaml :::\n\t- [", "version: 2\n", "profiles: {authoring: 7}", "profiles: []"):
        path = tmp_path / "b.yaml"
        path.write_text(text, encoding="utf-8")
        loaded = load_budgets(path, "GAP_ANALYSIS")
        assert loaded.max_wall_seconds == default.max_wall_seconds and loaded.defaulted, text


def test_invalid_values_are_clamped_to_defaults_and_reported(tmp_path: Path) -> None:
    path = tmp_path / "b.yaml"
    path.write_text(
        "version: 2\nprofiles:\n  authoring:\n    max_tool_calls: 0\n    max_wall_seconds: 'soon'\n"
        "    max_tokens: 5000\n    retry: {max_attempts: 99, backoff_seconds: [-1]}\n"
        "    circuit_breaker: {failure_threshold: 0, open_seconds: 5}\n", encoding="utf-8")
    loaded = load_budgets(path, "GAP_ANALYSIS")
    assert loaded.max_tool_calls == Budgets().max_tool_calls and loaded.max_wall_seconds == Budgets().max_wall_seconds
    assert loaded.max_tokens == 5000 and loaded.open_seconds == 5.0
    assert loaded.retry_attempts == Budgets().retry_attempts and loaded.failure_threshold == Budgets().failure_threshold
    assert {"max_tool_calls", "max_wall_seconds", "retry.max_attempts", "retry.backoff_seconds",
            "circuit_breaker.failure_threshold"} <= set(loaded.defaulted)


def test_a_version_1_file_still_loads_with_retry_defaults(tmp_path: Path) -> None:
    path = tmp_path / "b.yaml"
    path.write_text("version: 1\nprofiles:\n  authoring:\n    max_turns: 18\n    max_tool_calls: 24\n    max_wall_seconds: 900\n",
                    encoding="utf-8")
    loaded = load_budgets(path, "GAP_ANALYSIS")
    assert loaded.max_tool_calls == 24 and loaded.retry_attempts == 3 and "retry.max_attempts" in loaded.defaulted


# ---- tracker --------------------------------------------------------------------------------------
def test_tracker_reports_the_first_exhausted_budget() -> None:
    clock = FakeClock()
    tracker = BudgetTracker(Budgets(max_tool_calls=2, max_wall_seconds=10, max_tokens=100), clock)
    assert tracker.exceeded() is None
    tracker.add_tool_call(2)
    assert tracker.exceeded() is None                      # at the limit is still allowed
    tracker.add_tool_call()
    assert tracker.exceeded() == "TOOL_BUDGET_EXCEEDED"
    tracker.tool_calls = 0
    tracker.add_tokens(101)
    assert tracker.exceeded() == "TOKEN_BUDGET_EXCEEDED"
    tracker.tokens = 0
    clock.t = 11
    assert tracker.exceeded() == "WALL_TIMEOUT"
    assert tracker.snapshot() == {"tool_calls": 0, "max_tool_calls": 2, "elapsed_s": 11, "max_wall_s": 10,
                                  "tokens": 0, "max_tokens": 100}


# ---- circuit breaker ------------------------------------------------------------------------------
def test_breaker_opens_after_threshold_half_opens_then_closes() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(3, 120.0, clock)
    assert breaker.state == "closed" and breaker.allow()
    assert breaker.failure() is False and breaker.failure() is False
    assert breaker.failure() is True and breaker.state == "open" and not breaker.allow()
    assert breaker.reopens_in() == 120
    clock.t = 119
    assert breaker.state == "open"
    clock.t = 121
    assert breaker.state == "half_open" and breaker.allow()
    breaker.success()
    assert breaker.state == "closed" and breaker.reopens_in() == 0
    breaker.failure()
    breaker.success()
    assert breaker.failure() is False  # a success resets the consecutive count


# ---- retry ----------------------------------------------------------------------------------------
def test_retry_succeeds_after_transient_failures_with_the_configured_backoff() -> None:
    clock, calls, retries = FakeClock(), [], []
    outcomes = [err(), err(), "done"]

    def fn() -> str:
        calls.append(1)
        value = outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    result = call_with_retry(fn, target="deerflow", budgets=Budgets(), clock=clock,
                             on_retry=lambda attempt, reason: retries.append((attempt, reason)))
    assert result == "done" and len(calls) == 3
    assert clock.sleeps == [2.0, 5.0]
    assert retries == [(2, "HTTP_503"), (3, "HTTP_503")]


def test_retries_exhausted_when_the_breaker_does_not_trip_first() -> None:
    clock = FakeClock()

    def fn() -> None:
        raise err()

    with pytest.raises(RuntimeFailure) as info:
        call_with_retry(fn, target="deerflow", budgets=Budgets(), clock=clock,
                        breaker=CircuitBreaker(10, 120.0, clock))
    assert info.value.reason == "RETRIES_EXHAUSTED" and clock.sleeps == [2.0, 5.0]


def test_the_breaker_trips_before_retries_run_out_and_blocks_later_calls() -> None:
    clock, opened = FakeClock(), []
    breaker = CircuitBreaker(3, 120.0, clock)
    calls = []

    def fn() -> None:
        calls.append(1)
        raise err()

    with pytest.raises(RuntimeFailure) as info:
        call_with_retry(fn, target="deerflow", budgets=Budgets(), clock=clock, breaker=breaker,
                        on_circuit_open=opened.append)
    assert info.value.reason == "CIRCUIT_OPEN" and len(calls) == 3 and opened == [120]
    with pytest.raises(RuntimeFailure) as info:                         # next call does not even try
        call_with_retry(fn, target="deerflow", budgets=Budgets(), clock=clock, breaker=breaker)
    assert info.value.reason == "CIRCUIT_OPEN" and len(calls) == 3
    clock.t += 121                                                        # half-open: one probe is allowed
    assert call_with_retry(lambda: "ok", target="deerflow", budgets=Budgets(), clock=clock, breaker=breaker) == "ok"
    assert breaker.state == "closed"


def test_non_retryable_errors_surface_immediately_and_do_not_trip_the_breaker() -> None:
    clock, calls = FakeClock(), []
    breaker = CircuitBreaker(1, 120.0, clock)

    def fn() -> None:
        calls.append(1)
        raise err(retryable=False, reason="AUTH_FAILED")

    with pytest.raises(UpstreamError) as info:
        call_with_retry(fn, target="deerflow", budgets=Budgets(), clock=clock, breaker=breaker)
    assert info.value.reason == "AUTH_FAILED" and len(calls) == 1 and clock.sleeps == [] and breaker.state == "closed"


def test_cancellation_interrupts_a_backoff_and_stops_retrying() -> None:
    cancel, calls = CancelToken(), []

    class CancellingClock(FakeClock):
        def sleep(self, seconds: float, cancel: CancelToken | None = None) -> None:
            super().sleep(seconds)
            if cancel is not None:
                cancel.cancel("user")

    def fn() -> None:
        calls.append(1)
        raise err()

    with pytest.raises(RunCancelled):
        call_with_retry(fn, target="deerflow", budgets=Budgets(), clock=CancellingClock(), cancel=cancel)
    assert len(calls) == 1


def test_cancel_token() -> None:
    token = CancelToken()
    token.check()
    token.cancel("user")
    token.cancel("shutdown")           # the first reason sticks
    assert token.cancelled and token.reason == "user" and token.wait(0)
    with pytest.raises(RunCancelled):
        token.check()
