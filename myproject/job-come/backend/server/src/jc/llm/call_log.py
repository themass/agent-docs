"""Persist LLM call audit records.

Why this lives in `jc.llm` and not `jc.services`: it is the sink the LiteLLM
callbacks write into, and `jc.llm.audit_hook`, `jc.llm.call_context` and
`jc.llm.router` all need it. A model-transport layer that has to import a business
service to log a call has its dependencies upside down — the audit log is
infrastructure, not business orchestration.

Why this owns its own database session: `release_db_connection` requires callers
to end their read transaction *before* a slow model call, because resume
generation runs for minutes and a remote MySQL server will drop the socket.  By
the time there is something to log, the request's session has already been
rolled back and must not be reused.  Every write here opens a short session of
its own and commits immediately.

Logging never raises. A broken audit log must not turn a working resume into an
error page, so every public entry point swallows its own failures into a warning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agentkit.common.ids import new_id

from jc.config import settings
from jc.models.llm_call import LlmCall, LlmCallAttempt

logger = logging.getLogger(__name__)

_ERROR_MESSAGE_MAX = 1024


@dataclass(slots=True)
class LLMLogContext:
    """Business identity for one logical call. Passed explicitly, never inferred.

    Explicit beats a ContextVar here: the call sites are few (one per service),
    and the agent path runs the model in a worker thread, where a request-scoped
    ContextVar set by middleware is not visible anyway.
    """

    caller: str
    user_id: str | None = None
    actor_kind: str | None = None
    profile_id: str | None = None
    job_id: str | None = None
    session_id: str | None = None
    skill_hint: str | None = None


@dataclass(slots=True)
class AttemptRecord:
    """One endpoint attempt, successful or not."""

    attempt_index: int
    model: str
    provider: str | None = None
    api_base_env: str | None = None
    status: str = "failed"
    error_code: str | None = None
    error_message: str | None = None
    validator_failed: bool = False
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_micro_usd: int | None = None


@dataclass(slots=True)
class CallRecord:
    """One logical call: a scenario resolved through its failover chain."""

    scenario: str
    context: LLMLogContext
    channel: str = "router"
    status: str = "failed"
    final_model: str | None = None
    final_provider: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    trace_id: str | None = None
    stream: bool = False
    prompt_text: str | None = None
    response_text: str | None = None
    reasoning_text: str | None = None
    attempts: list[AttemptRecord] = field(default_factory=list)


def error_code_for(exc: BaseException) -> str:
    """Stable, low-cardinality reason code suitable for grouping in a dashboard.

    The exception message is not usable as a grouping key: gateways embed request
    ids and model names in it. The class name is stable, and the few cases JC
    cares about separately are named here.
    """
    name = type(exc).__name__
    text = str(exc).lower()
    # Our own validator rejected a 200 response. Checked before the generic
    # rules because litellm wraps it as APIResponseValidationError, which would
    # otherwise group a model-quality problem with transport problems.
    if "jc_invalid_response" in text:
        return "invalid_response"
    if "empty_model_response" in text:
        return "empty_model_response"
    if "invalid_json_response" in text or (isinstance(exc, ValueError) and "json" in text):
        return "invalid_json_response"
    if "timeout" in name.lower() or "timed out" in text:
        return "timeout"
    if "ratelimit" in name.lower() or "429" in text:
        return "rate_limited"
    if "authentication" in name.lower() or "401" in text:
        return "auth_failed"
    if "connection" in name.lower() or "nodename nor servname" in text:
        return "unreachable"
    return name


def truncate_error(message: str | None) -> str | None:
    if not message:
        return None
    text = " ".join(message.split())
    if len(text) <= _ERROR_MESSAGE_MAX:
        return text
    return text[: _ERROR_MESSAGE_MAX - 3] + "..."


def _clip_payload(text: str | None) -> tuple[str | None, bool]:
    if not text:
        return None, False
    limit = max(0, settings.jc_llm_log_payload_max_chars)
    if limit == 0:
        return None, False
    if len(text) <= limit:
        return text, False
    half = limit // 2
    clipped = f"{text[:half]}\n...[truncated {len(text) - limit} chars]...\n{text[-half:]}"
    return clipped, True


def _sum(values: list[int | None]) -> int | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _rows_from(record: CallRecord) -> tuple[LlmCall, list[LlmCallAttempt]]:
    call_id = new_id("llmc")
    ctx = record.context
    prompt_text = response_text = reasoning_text = None
    truncated = False
    if settings.jc_llm_log_payload:
        prompt_text, t1 = _clip_payload(record.prompt_text)
        response_text, t2 = _clip_payload(record.response_text)
        reasoning_text, t3 = _clip_payload(record.reasoning_text)
        truncated = t1 or t2 or t3

    call = LlmCall(
        id=call_id,
        user_id=ctx.user_id,
        actor_kind=ctx.actor_kind,
        profile_id=ctx.profile_id,
        job_id=ctx.job_id,
        session_id=ctx.session_id,
        scenario=record.scenario,
        caller=ctx.caller,
        channel=record.channel,
        skill_hint=ctx.skill_hint,
        status=record.status,
        final_model=record.final_model,
        final_provider=record.final_provider,
        attempt_count=len(record.attempts),
        error_code=record.error_code,
        error_message=truncate_error(record.error_message),
        latency_ms=record.latency_ms,
        prompt_tokens=_sum([a.prompt_tokens for a in record.attempts]),
        completion_tokens=_sum([a.completion_tokens for a in record.attempts]),
        reasoning_tokens=_sum([a.reasoning_tokens for a in record.attempts]),
        total_tokens=_sum([a.total_tokens for a in record.attempts]),
        cost_micro_usd=_sum([a.cost_micro_usd for a in record.attempts]),
        trace_id=record.trace_id,
        stream=record.stream,
        prompt_text=prompt_text,
        response_text=response_text,
        reasoning_text=reasoning_text,
        payload_truncated=truncated,
    )
    attempts = [
        LlmCallAttempt(
            id=new_id("llma"),
            call_id=call_id,
            attempt_index=a.attempt_index,
            model=a.model,
            provider=a.provider,
            api_base_env=a.api_base_env,
            status=a.status,
            error_code=a.error_code,
            error_message=truncate_error(a.error_message),
            validator_failed=a.validator_failed,
            latency_ms=a.latency_ms,
            prompt_tokens=a.prompt_tokens,
            completion_tokens=a.completion_tokens,
            reasoning_tokens=a.reasoning_tokens,
            total_tokens=a.total_tokens,
            cost_micro_usd=a.cost_micro_usd,
        )
        for a in record.attempts
    ]
    return call, attempts


async def record_call(record: CallRecord) -> str | None:
    """Write one call plus its attempts. Returns the call id, or None if skipped."""
    if not settings.jc_llm_log_enabled:
        return None
    try:
        from jc.db.session import AsyncSessionLocal

        call, attempts = _rows_from(record)
        async with AsyncSessionLocal() as session:
            session.add(call)
            for row in attempts:
                session.add(row)
            await session.commit()
        return call.id
    except Exception:  # noqa: BLE001
        # An unreachable or slow audit table must never fail the user's request.
        logger.warning(
            "LLM call log write failed (scenario=%s caller=%s)",
            record.scenario,
            record.context.caller,
            exc_info=True,
        )
        return None


def usage_from_response(response: Any) -> dict[str, int | None]:
    """Read token usage from an OpenAI-compatible response, tolerating shapes.

    Gateways disagree on where reasoning tokens live: some nest them under
    `completion_tokens_details.reasoning_tokens`, some expose a flat
    `reasoning_tokens`. Both are accepted; a missing value stays None rather
    than becoming a misleading zero.
    """
    usage = _get(response, "usage")
    if usage is None:
        return {}
    details = _get(usage, "completion_tokens_details")
    reasoning = _int(_get(details, "reasoning_tokens")) if details is not None else None
    if reasoning is None:
        reasoning = _int(_get(usage, "reasoning_tokens"))
    return {
        "prompt_tokens": _int(_get(usage, "prompt_tokens")),
        "completion_tokens": _int(_get(usage, "completion_tokens")),
        "reasoning_tokens": reasoning,
        "total_tokens": _int(_get(usage, "total_tokens")),
    }


def cost_micro_usd(response: Any) -> int | None:
    """Cost of one attempt in micro-USD, or `None` when the model has no price.

    Two sources, in this order:

    1. **`pricing:` in `routing.yaml`** (`jc.llm.pricing`). Every model this product
       actually calls is reached through a gateway under a vendor-neutral name, and
       none of those names exist in litellm's bundled price map — so without this the
       admin 花费 column was empty for every row ever logged.
    2. **litellm's local cost map**, for public model names that are in it.

    `None` rather than 0 when neither knows the model: an empty cell says "unpriced",
    a 0 would claim the call was free, and a cost report must not blur those.
    """
    served = _served_model_name(response)
    try:
        from jc.llm.router import get_llm_router

        price = get_llm_router().price_for_model(served)
    except Exception:  # noqa: BLE001
        price = None
    if price is not None:
        usage = usage_from_response(response)
        configured = price.micro_usd(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
        if configured is not None:
            return configured

    try:
        import litellm

        cost = litellm.completion_cost(completion_response=response)
    except Exception:  # noqa: BLE001
        return None
    if not cost:
        return None
    return int(round(float(cost) * 1_000_000))


def _served_model_name(response: Any) -> str | None:
    """The model the gateway says answered, which is what carries the price."""
    model = _get(response, "model")
    return str(model) if model else None


def reasoning_from_response(response: Any) -> str | None:
    """Extract chain-of-thought text when the gateway returns it."""
    choices = _get(response, "choices")
    if not isinstance(choices, (list, tuple)) or not choices:
        return None
    message = _get(choices[0], "message")
    if message is None:
        return None
    for name in ("reasoning_content", "reasoning"):
        value = _get(message, name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def prompt_text_from_messages(messages: list[dict[str, Any]]) -> str:
    """Flatten a chat request for storage, dropping base64 image bytes.

    Vision calls carry megabytes of inlined image data. Storing that would make
    the audit table unusable while adding nothing a human would read.
    """
    parts: list[str] = []
    for message in messages or []:
        role = str(message.get("role", "?"))
        parts.append(f"[{role}]\n{_flatten_content(message.get('content'))}")
    return "\n\n".join(parts)


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if content.get("type") == "image_url":
            return "<image omitted>"
        text = content.get("text")
        return text if isinstance(text, str) else ""
    if isinstance(content, (list, tuple)):
        return "\n".join(_flatten_content(part) for part in content)
    return ""


def _get(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
