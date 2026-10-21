"""LLM audit as an observer, not as router code.

Why this is not inline
----------------------
The first implementation wrote audit rows inside ``LLMRouter``'s retry loop.
That put three concerns in one function - choosing an endpoint, calling it, and
recording what happened - so the loop could not change without touching the log,
and the log could not be reused by any other caller. The DeerFlow path could not
use it at all, because the harness does not go through ``LLMRouter``.

Who reports what, and why it is split
-------------------------------------
litellm fires its **failure** event inline, on the calling thread, before the
next fallback is attempted. Its **success** event is handed to a background
logging worker (``litellm_core_utils/logging_worker.py``), which runs it later -
*after* the caller has already received the response and closed its audit scope.
Measured, not assumed: an earlier revision collected both from callbacks and
every recovered chain was recorded as a failure, because the success event
arrived after the row was written.

So the split follows what each side can actually know in time:

* **Failures** come from the callback. It is inline, and it is the only place
  that sees the attempts the caller never gets a response for.
* **Success** is reported by the caller through `report_success`, which holds
  the response object and therefore knows the served model, the usage, and the
  cost without waiting for anything.

What this deliberately does not do
----------------------------------
It does not decide JC's notion of failure. A gateway 200 carrying unusable JSON
is a success to litellm and a failure to JC. That verdict is reached inside
litellm's call stack by `jc.llm.transport.validation_rule`, so it arrives here
as an ordinary failure event - which is what makes the chain fail over, instead
of this module learning to second-guess a response it was only meant to observe.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from litellm.integrations.custom_logger import CustomLogger

from jc.llm.call_context import llm_context
from jc.llm.call_log import (
    AttemptRecord,
    CallRecord,
    cost_micro_usd,
    error_code_for,
    prompt_text_from_messages,
    reasoning_from_response,
    record_call,
    truncate_error,
    usage_from_response,
)
from jc.llm.transport import VALIDATION_ERROR_MARKER

logger = logging.getLogger(__name__)


@dataclass
class _CallScope:
    """One logical call: a scenario resolved through its failover chain."""

    scenario: str
    caller: str
    channel: str
    attempts: list[AttemptRecord] = field(default_factory=list)
    prompt_text: str | None = None
    response_text: str | None = None
    reasoning_text: str | None = None
    final_model: str | None = None
    final_provider: str | None = None
    status: str = "failed"
    error_code: str | None = None
    error_message: str | None = None
    stream: bool = False
    trace_id: str | None = None
    started: float = field(default_factory=time.monotonic)


#: The logical call in flight.
#:
#: litellm fires one event per *physical* attempt, so a chain that fails over
#: emits several. Without a boundary the audit table gets a row per attempt,
#: which double counts cost and makes "how many calls failed" unanswerable. The
#: caller knows the boundary, so it declares it; the hook only collects.
#:
#: A ContextVar rather than a thread-local because litellm dispatches callbacks
#: through ``contextvars.copy_context()`` onto other threads, where a
#: thread-local scope is invisible and the attempt would escape as its own row.
#: The var holds a mutable object, so collecting from a copied context still
#: mutates the one scope.
_scope_var: ContextVar[_CallScope | None] = ContextVar("jc_llm_call_scope", default=None)


def current_scope() -> _CallScope | None:
    return _scope_var.get()


@contextmanager
def sync_call_scope(
    scenario: str, caller: str, channel: str = "router", *, stream: bool = False
) -> Iterator[_CallScope]:
    """`llm_call_scope` for synchronous callers (the harness streams this way).

    The row is handed to `record_call` by the async caller; here there may be no
    running loop, so the scope is flushed through the same sink the harness uses
    for its other cross-thread traffic.
    """
    scope = _CallScope(scenario=scenario, caller=caller, channel=channel, stream=stream)
    token = _scope_var.set(scope)
    try:
        yield scope
    except BaseException as exc:
        _note_unobserved_exit(scope, exc)
        raise
    finally:
        _scope_var.reset(token)
        _flush_sync(scope)


@asynccontextmanager
async def llm_call_scope(
    scenario: str, caller: str, channel: str = "router", *, stream: bool = False
) -> AsyncIterator[_CallScope]:
    """Declare one logical call, so its attempts collapse into a single row."""
    scope = _CallScope(scenario=scenario, caller=caller, channel=channel, stream=stream)
    token = _scope_var.set(scope)
    try:
        yield scope
    except BaseException as exc:
        _note_unobserved_exit(scope, exc)
        raise
    finally:
        _scope_var.reset(token)
        try:
            await record_call(record_from_scope(scope))
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM audit flush failed: %s", exc)


#: Where `sync_call_scope` sends finished rows. The harness installs a sink that
#: hands them to its request loop, because the async database engine's pool
#: belongs to that loop and is not usable from the streaming worker thread.
_sink_var: ContextVar[Any] = ContextVar("jc_llm_audit_sink", default=None)


@contextmanager
def audit_sink(sink: Any) -> Iterator[None]:
    """Route rows finished on this thread to `sink` instead of the database."""
    token = _sink_var.set(sink)
    try:
        yield
    finally:
        _sink_var.reset(token)


def _flush_sync(scope: _CallScope) -> None:
    record = record_from_scope(scope)
    sink = _sink_var.get()
    if sink is None:
        # No consumer on this thread. Dropping beats raising: auditing must
        # never break the call it observes.
        logger.debug("LLM audit row dropped (no sink): scenario=%s", scope.scenario)
        return
    try:
        sink(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM audit sink failed: %s", exc)


def report_success(
    response: Any,
    *,
    provider: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Record the attempt that succeeded, from the caller that holds the response.

    Not taken from litellm's success callback: that one runs on a background
    logging worker and arrives after the caller has closed its scope, so a
    recovered chain would be filed as a failure.
    """
    scope = _scope_var.get()
    if scope is None:
        return
    served = _served_model(response) or "unknown"
    usage = usage_from_response(response)
    scope.attempts.append(
        AttemptRecord(
            attempt_index=len(scope.attempts),
            model=served,
            provider=provider,
            status="success",
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            reasoning_tokens=usage.get("reasoning_tokens"),
            total_tokens=usage.get("total_tokens"),
            cost_micro_usd=cost_micro_usd(response),
        )
    )
    scope.status = "success"
    scope.final_model = served
    scope.final_provider = provider
    scope.response_text = _response_text(response)
    scope.reasoning_text = reasoning_from_response(response)
    scope.error_code = None
    scope.error_message = None


def report_attempt_failure(
    exc: Exception, *, model: str, provider: str | None,
    latency_ms: int, validator_failed: bool = False,
) -> None:
    """Failures raised while consuming/validating an owned structured stream."""
    scope = _scope_var.get()
    if scope is None:
        return
    attempt = AttemptRecord(
        attempt_index=len(scope.attempts), model=model, provider=provider,
        latency_ms=latency_ms, validator_failed=validator_failed,
        error_code="invalid_response" if validator_failed else error_code_for(exc),
        # A validator can contain PII in its error. Persist a type, not the body.
        error_message=type(exc).__name__,
    )
    scope.attempts.append(attempt)
    scope.error_code = attempt.error_code
    scope.error_message = attempt.error_message


def report_stream_opened(stream: Any, *, provider: str | None = None) -> None:
    """Record that a stream opened successfully.

    Streamed rows carry no token counts: the caller owns the iterator, so at the
    only moment this code runs the final text does not exist yet. That absence is
    what separates a streamed row from a unary one in a cost report.
    """
    scope = _scope_var.get()
    if scope is None:
        return
    served = _served_model(stream) or "unknown"
    scope.attempts.append(
        AttemptRecord(
            attempt_index=len(scope.attempts),
            model=served,
            provider=provider,
            status="success",
        )
    )
    scope.status = "success"
    scope.final_model = served
    scope.final_provider = provider
    scope.error_code = None
    scope.error_message = None


def report_skipped(skipped: Any) -> None:
    """Record endpoints that were never called because their key is unset.

    Written as `skipped` attempts rather than omitted so the row still explains
    why the answer came from the second model. Left out of the failure counts:
    nothing was attempted, so nothing failed.
    """
    scope = _scope_var.get()
    if scope is None:
        return
    for endpoint in skipped or ():
        scope.attempts.append(
            AttemptRecord(
                attempt_index=len(scope.attempts),
                model=endpoint.model,
                provider=endpoint.provider,
                api_base_env=endpoint.api_key_env,
                status="skipped",
                error_code="missing_api_key",
            )
        )


def report_prompt(messages: list[dict[str, Any]], *, trace_id: str | None = None) -> None:
    """Attach the prompt to the scope.

    Taken from the caller rather than the callback because a scope whose every
    attempt failed still wants the prompt - that is the row someone will be
    reading when they ask why the call failed.
    """
    scope = _scope_var.get()
    if scope is None:
        return
    if scope.prompt_text is None:
        scope.prompt_text = prompt_text_from_messages(messages)
    if trace_id and not scope.trace_id:
        scope.trace_id = trace_id


def _note_unobserved_exit(scope: _CallScope, exc: BaseException) -> None:
    """Classify a scope that is leaving without ever calling `report_success`.

    Without this, a call torn down mid-flight files as a blank failure: no
    attempts (litellm's failure callback never fired, because nothing told
    litellm the call failed - the *caller's* awaiting task was destroyed out
    from under it), no error_code, no error_message. That blank row is what
    `jc_llm_call` showed for three real calls with 180s-405s of latency and
    zero attempts: the gateway was never asked "did this fail", the host task
    simply stopped waiting for its answer.

    `asyncio.CancelledError` is `BaseException`, not `Exception` - this must
    stay a `BaseException` handler or cancellation (steer/stop button/client
    disconnect/timeout) would silently fall through unclassified, which is
    the exact gap this closes. The exception is re-raised unchanged by the
    caller right after this returns; this function only records, it never
    suppresses or converts it.
    """
    if scope.status == "success":
        # A success was already reported and something failed on the way out
        # of the context (e.g. the audit flush itself). Leave the verdict the
        # caller already reached; just make sure the reason for the exit is
        # not silently lost from the row's error fields.
        return
    scope.status = "failed"
    if isinstance(exc, asyncio.CancelledError):
        scope.error_code = "cancelled"
        scope.error_message = "Call was cancelled before any endpoint reported success"
    else:
        scope.error_code = error_code_for(exc)
        scope.error_message = truncate_error(f"{type(exc).__name__}: {exc}")


def record_from_scope(scope: _CallScope) -> CallRecord:
    record = CallRecord(
        scenario=scope.scenario,
        context=llm_context(scope.caller),
        channel=scope.channel,
        status=scope.status,
        final_model=scope.final_model,
        final_provider=scope.final_provider,
        error_code=scope.error_code,
        error_message=scope.error_message,
        latency_ms=int((time.monotonic() - scope.started) * 1000),
        stream=scope.stream,
        prompt_text=scope.prompt_text,
        response_text=scope.response_text,
        reasoning_text=scope.reasoning_text,
        trace_id=scope.trace_id,
    )
    for index, attempt in enumerate(scope.attempts):
        attempt.attempt_index = index
        record.attempts.append(attempt)
    return record


class JCAuditLogger(CustomLogger):
    """Collects the failed attempts of the call currently in scope.

    Both the sync and async failure hooks are implemented because litellm picks
    one by call style, and the harness streams synchronously while the services
    are async.
    """

    def log_failure_event(
        self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        self._note_failure(kwargs, start_time, end_time)

    async def async_log_failure_event(
        self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any
    ) -> None:
        self._note_failure(kwargs, start_time, end_time)

    def _note_failure(self, kwargs: dict[str, Any], start_time: Any, end_time: Any) -> None:
        try:
            scope = _scope_var.get()
            if scope is None:
                return
            exception = _exception_from(kwargs)
            attempt = AttemptRecord(
                attempt_index=len(scope.attempts),
                model=_requested_model(kwargs),
                provider=_provider_from(kwargs),
                status="failed",
                latency_ms=_latency_ms(start_time, end_time),
            )
            if exception is not None:
                attempt.error_code = error_code_for(exception)
                attempt.error_message = f"{type(exception).__name__}: {exception}"
                # Our own validator rejected a 200. A model-quality signal, not
                # an availability one, and the two must stay distinguishable.
                attempt.validator_failed = VALIDATION_ERROR_MARKER in str(exception)
            scope.attempts.append(attempt)
            # Only while the call is still failing: a later success overwrites
            # this through `report_success`.
            if scope.status != "success":
                scope.status = "failed"
                scope.error_code = attempt.error_code or "unknown"
                scope.error_message = attempt.error_message
        except Exception as exc:  # noqa: BLE001
            # Auditing must never break the call it is observing.
            logger.warning("LLM audit callback failed: %s", exc)


def _requested_model(kwargs: dict[str, Any]) -> str:
    model = kwargs.get("model")
    if isinstance(model, str) and model:
        return model
    params = kwargs.get("litellm_params") or {}
    candidate = params.get("model")
    return candidate if isinstance(candidate, str) and candidate else "unknown"


def _provider_from(kwargs: dict[str, Any]) -> str | None:
    params = kwargs.get("litellm_params") or {}
    info = params.get("model_info")
    if isinstance(info, dict):
        provider = info.get("jc_provider")
        if isinstance(provider, str) and provider:
            return provider
    return None


def _served_model(response_obj: Any) -> str | None:
    if isinstance(response_obj, dict):
        model = response_obj.get("model")
    else:
        model = getattr(response_obj, "model", None)
    return model if isinstance(model, str) and model else None


def _response_text(response_obj: Any) -> str | None:
    from jc.llm.message_mapping import content_text

    if isinstance(response_obj, dict):
        choices = response_obj.get("choices")
    else:
        choices = getattr(response_obj, "choices", None)
    if not choices:
        return None
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else getattr(first, "message", None)
    if message is None:
        return None
    content = (
        message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
    )
    return content_text(content) or None


def _exception_from(kwargs: dict[str, Any]) -> BaseException | None:
    for key in ("exception", "original_exception", "error"):
        value = kwargs.get(key)
        if isinstance(value, BaseException):
            return value
    return None


def _latency_ms(start_time: Any, end_time: Any) -> int | None:
    if start_time is None or end_time is None:
        return None
    try:
        delta = end_time - start_time
    except TypeError:
        return None
    seconds = getattr(delta, "total_seconds", None)
    if callable(seconds):
        return int(seconds() * 1000)
    if isinstance(delta, (int, float)):
        return int(delta * 1000)
    return None


_registered = False


def register_audit_callback() -> bool:
    """Attach the audit observer to litellm once per process."""
    global _registered
    if _registered:
        return True
    from jc.config import settings

    if not settings.jc_llm_log_enabled:
        return False
    import litellm

    callbacks = list(litellm.callbacks or [])
    if not any(isinstance(item, JCAuditLogger) for item in callbacks):
        callbacks.append(JCAuditLogger())
        litellm.callbacks = callbacks
    _registered = True
    logger.info("JC LLM audit callback registered")
    return True
