"""Submit a run to DeerFlow, watch it under the run's budgets, and return the final AI message text.

Failure policy (contract D4): any failure raises ``RuntimeFailure`` with a short reason code. There is no
fallback to the STUB. Cancellation is checked at every poll and every backoff sleep.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agent_worker.deerflow.client import DeerFlowClient, DeerFlowError, thread_id_for
from agent_worker.governance import (
    Budgets,
    BudgetTracker,
    CancelToken,
    CircuitBreaker,
    RunCancelled,
    RuntimeFailure,
    UpstreamError,
    call_with_retry,
)

# Upstream 2.2.0 has no automatic model fallback (it only retries inside one model and trips its own
# breaker), so switching models is an explicit, visible worker decision: `context.model_name` + degraded=true.
FALLBACK_REASONS = {"DEERFLOW_RUN_ERROR", "MODEL_ERROR_FALLBACK"}
TERMINAL_FAILURE = {"error": "DEERFLOW_RUN_ERROR", "timeout": "DEERFLOW_RUN_TIMEOUT", "interrupted": "DEERFLOW_RUN_INTERRUPTED"}
BUDGET_EVENT_EVERY = 5.0


@dataclass
class Hooks:
    """Callbacks into the runner; every one is metadata-only."""
    event: Callable[[str, dict[str, Any]], None]
    admitted: Callable[[str, str], None]


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in (None, "text"):
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return ""


def _is_ai(row: dict[str, Any]) -> bool:
    return row.get("event_type") == "llm.ai.response"


def _final_candidate(row: dict[str, Any]) -> str | None:
    """Text of an AI message that ends the turn (no pending tool calls), else None."""
    content = row.get("content")
    if not isinstance(content, dict):
        return None
    if content.get("tool_calls"):
        return None
    text = _text_of(content.get("content")).strip()
    return text or None


class DeerFlowRuntime:
    def __init__(self, client: DeerFlowClient, breaker: CircuitBreaker, clock: Any) -> None:
        self.client = client
        self.breaker = breaker
        self.clock = clock

    def execute(
        self,
        *,
        run_id: str,
        body: dict[str, Any],
        budgets: Budgets,
        tracker: BudgetTracker,
        cancel: CancelToken,
        hooks: Hooks,
        poll_interval: float,
    ) -> str:
        """Primary model first; once, on a model-side failure, the configured fallback model (if any)."""
        fallback = self.client.config.fallback_model
        attempts: list[str | None] = [None] + ([fallback] if fallback else [])
        for index, model in enumerate(attempts):
            try:
                return self._attempt(run_id=run_id, body=body, budgets=budgets, tracker=tracker, cancel=cancel,
                                     hooks=hooks, poll_interval=poll_interval, model=model, degraded=index > 0)
            except RuntimeFailure as exc:
                if index + 1 < len(attempts) and exc.reason in FALLBACK_REASONS and not cancel.cancelled \
                        and tracker.exceeded() is None:
                    hooks.event("RETRY", {"attempt": index + 2, "reason": f"MODEL_FALLBACK:{exc.reason}",
                                          "target": "deerflow", "op": "switch_model"})
                    continue
                raise
        raise RuntimeFailure("NO_FINAL_MESSAGE")  # unreachable: the loop always returns or raises

    def _attempt(
        self,
        *,
        run_id: str,
        body: dict[str, Any],
        budgets: Budgets,
        tracker: BudgetTracker,
        cancel: CancelToken,
        hooks: Hooks,
        poll_interval: float,
        model: str | None,
        degraded: bool,
    ) -> str:
        def guarded(fn: Callable[[], Any], op: str) -> Any:
            try:
                return call_with_retry(
                    fn, target="deerflow", budgets=budgets, breaker=self.breaker, clock=self.clock, cancel=cancel,
                    on_retry=lambda attempt, reason: hooks.event("RETRY", {"attempt": attempt, "reason": reason, "target": "deerflow", "op": op}),
                    on_circuit_open=lambda secs: hooks.event("CIRCUIT_OPEN", {"target": "deerflow", "reopens_in_s": secs}),
                )
            except DeerFlowError as exc:  # non-retryable
                raise RuntimeFailure({"AUTH_FAILED": "DEERFLOW_AUTH_FAILED", "CONFLICT": "DEERFLOW_CONFLICT",
                                      "NOT_FOUND": "DEERFLOW_NOT_FOUND"}.get(exc.reason, "DEERFLOW_REJECTED")) from exc
            except UpstreamError as exc:
                raise RuntimeFailure("DEERFLOW_REJECTED") from exc

        suffix = "-fb" if degraded else ""
        thread_id = thread_id_for(run_id + suffix)
        guarded(lambda: self.client.ensure_thread(thread_id, {"poetry_run_id": run_id}), "ensure_thread")
        payload = dict(body)
        payload["assistant_id"] = self.client.config.assistant_id
        if model:
            payload["context"] = {"model_name": model}
        created = guarded(lambda: self.client.create_run(thread_id, payload, f"poetry-worker:{run_id}{suffix}"), "create_run")
        runtime_run_id = str(created["run_id"])
        hooks.admitted(thread_id, runtime_run_id)
        hooks.event("STEP", {"name": "deerflow_submitted", "detail": "run admitted"})

        def monitor() -> str:
            seen_seq = 0
            tool_calls_seen = 0
            last_budget_at = self.clock.now()
            last_budget_key: tuple[int, int] = (-1, -1)
            final_text: str | None = None
            final_degraded = False

            def drain() -> None:
                nonlocal seen_seq, tool_calls_seen, final_text, final_degraded
                rows = guarded(lambda: self.client.list_messages(thread_id, runtime_run_id, seen_seq or None), "messages")
                for row in rows:
                    seq = row.get("seq")
                    if isinstance(seq, int):
                        seen_seq = max(seen_seq, seq)
                    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
                    if row.get("event_type") == "llm.tool.result":
                        tool_calls_seen += 1
                        tracker.add_tool_call()
                        content = row.get("content") if isinstance(row.get("content"), dict) else {}
                        status = str(content.get("status") or "success")
                        hooks.event("TOOL_CALL", {"tool": str(content.get("name") or "unknown")[:64],
                                                  "outcome": "error" if status == "error" else "ok", "ms": None})
                    elif _is_ai(row):
                        content = row.get("content") if isinstance(row.get("content"), dict) else {}
                        usage = content.get("usage_metadata") if isinstance(content.get("usage_metadata"), dict) else {}
                        tin, tout = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
                        tracker.add_tokens(int(usage.get("total_tokens") or (tin + tout)))
                        is_degraded = degraded or meta.get("status") == "fallback"
                        hooks.event("MODEL_USAGE", {"model": str(meta.get("model") or "unknown")[:80], "input_tokens": tin,
                                                    "output_tokens": tout, "ms": None, "degraded": is_degraded})
                        candidate = _final_candidate(row)
                        if candidate is not None:
                            final_text, final_degraded = candidate, meta.get("status") == "fallback"

            def check_limits() -> None:
                reason = tracker.exceeded()
                if reason:
                    try:
                        self.client.cancel(thread_id, runtime_run_id)
                    except UpstreamError:
                        pass
                    raise RuntimeFailure(reason)

            while True:
                cancel.check()
                run = guarded(lambda: self.client.get_run(thread_id, runtime_run_id), "get_run")
                drain()
                status = str(run.get("status"))
                if status in TERMINAL_FAILURE:
                    raise RuntimeFailure(TERMINAL_FAILURE[status])
                if status == "success":
                    break
                check_limits()
                now = self.clock.now()
                key = (tracker.tool_calls, tracker.tokens)
                if key != last_budget_key and now - last_budget_at >= BUDGET_EVENT_EVERY:
                    hooks.event("BUDGET_UPDATE", tracker.snapshot())
                    last_budget_key, last_budget_at = key, now
                self.clock.sleep(poll_interval, cancel)

            drain()  # catch messages written between the last poll and completion
            reported = int(run.get("total_tokens") or 0)
            if reported > tracker.tokens:
                tracker.add_tokens(reported - tracker.tokens)
            cancel.check()
            if final_text is None:
                raise RuntimeFailure("NO_FINAL_MESSAGE")
            if final_degraded:
                raise RuntimeFailure("MODEL_ERROR_FALLBACK")
            return final_text

        try:
            return monitor()
        except RunCancelled:
            # Editor cancel or worker shutdown: stop the remote run too, best effort. The run's output is
            # dropped either way; this just stops it spending tokens.
            try:
                self.client.cancel(thread_id, runtime_run_id)
            except UpstreamError:
                pass
            raise
