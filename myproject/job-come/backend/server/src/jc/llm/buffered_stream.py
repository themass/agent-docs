"""Collect structured streaming responses without exposing partial JSON as success.

The configured transport still owns credentials, aliases and connection pools.
Unlike an open agent stream, this operation owns consumption and validation, so
failover must include failures *after* headers arrive. Each alias is tried once.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

from jc.llm.transport import ScenarioTransport, complete_deployment_once

logger = logging.getLogger(__name__)


class IncompleteStructuredStream(ValueError):
    """An interrupted/truncated stream must not become a saved profile."""


async def collect_completion(
    transport: ScenarioTransport,
    kwargs: dict[str, Any],
    validator: Callable[[Any], Any] | None,
    *,
    attempt_timeout_seconds: float | None = None,
) -> tuple[Any, Any]:
    from litellm import stream_chunk_builder

    from jc.llm import audit_hook

    last_error: Exception | None = None
    last_validation_error: Exception | None = None
    for deployment in transport.deployments or transport.router.model_list:
        alias = deployment["model_name"]
        model = deployment["litellm_params"]["model"]
        provider = deployment.get("model_info", {}).get("jc_provider") or None
        started = time.monotonic()
        stream = None
        chunks = []
        finished = False
        validating = False
        content_chars = 0
        reasoning_chars = 0
        last_progress = started
        scope = audit_hook.current_scope()
        observed = len(scope.attempts) if scope else 0
        logger.info("llm_buffered_stream alias=%s model=%s phase=start", alias, model)
        try:
            async with asyncio.timeout(attempt_timeout_seconds):
                # No nested fallback: a failure during consumption must advance from
                # this alias, not restart the primary or repeat an already failed model.
                stream = await complete_deployment_once(
                    deployment,
                    {**kwargs, "stream": True, "stream_options": {"include_usage": True}},
                )
                idle_timeout = kwargs.get("timeout") or deployment["litellm_params"]["timeout"]
                iterator = aiter(stream)
                while True:
                    try:
                        async with asyncio.timeout(idle_timeout):
                            chunk = await anext(iterator)
                    except StopAsyncIteration:
                        break
                    if not chunks:
                        logger.info(
                            "llm_buffered_stream alias=%s phase=first_chunk elapsed_ms=%d",
                            alias,
                            int((time.monotonic() - started) * 1000),
                        )
                    chunks.append(chunk)
                    for choice in chunk.choices:
                        delta = choice.delta
                        content = getattr(delta, "content", None)
                        reasoning = getattr(delta, "reasoning_content", None)
                        if isinstance(content, str):
                            content_chars += len(content)
                        if isinstance(reasoning, str):
                            reasoning_chars += len(reasoning)
                        reason = choice.finish_reason
                        if reason is not None:
                            if reason != "stop":
                                raise IncompleteStructuredStream(f"stream_finish_{reason}")
                            finished = True
                    if time.monotonic() - last_progress >= 10:
                        last_progress = time.monotonic()
                        logger.info(
                            "llm_buffered_stream alias=%s phase=receiving chunks=%d "
                            "content_chars=%d reasoning_chars=%d elapsed_ms=%d",
                            alias, len(chunks), content_chars, reasoning_chars,
                            int((last_progress - started) * 1000),
                        )
                if not chunks or not finished:
                    raise IncompleteStructuredStream("stream_ended_without_stop")
                response = stream_chunk_builder(chunks, messages=kwargs.get("messages"))
                validating = True
                result = validator(response) if validator else None
                logger.info(
                    "llm_buffered_stream alias=%s phase=validated chunks=%d elapsed_ms=%d",
                    alias,
                    len(chunks),
                    int((time.monotonic() - started) * 1000),
                )
                return response, result
        except Exception as exc:
            # SDK stream errors may wrap the original provider error. Preserve
            # its category while keeping raw messages/resume text out of logs.
            from litellm.exceptions import MidStreamFallbackError

            if isinstance(exc, MidStreamFallbackError) and exc.original_exception is not None:
                exc = exc.original_exception
            last_error = exc
            if validating:
                # A validly received response that failed the domain contract is more
                # actionable than a later provider outage; preserve it for the caller.
                last_validation_error = exc
            # Transport callbacks see connection failures, but not a validator
            # rejecting already-consumed JSON. Do not silently lose that attempt.
            if scope is not None and len(scope.attempts) == observed:
                audit_hook.report_attempt_failure(
                    exc,
                    model=model,
                    provider=provider,
                    validator_failed=validating,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            logger.warning(
                "llm_buffered_stream alias=%s phase=failed error_type=%s reason=%s elapsed_ms=%d "
                "chunks=%d content_chars=%d reasoning_chars=%d",
                alias,
                type(exc).__name__,
                str(exc) if type(exc).__name__ == "ProfileStructureError" and str(exc) in {
                    "invalid_profile_schema", "invalid_json_response", "empty_model_response",
                    "invalid_json_object", "empty_profile_response",
                } else "redacted",
                int((time.monotonic() - started) * 1000),
                len(chunks), content_chars, reasoning_chars,
            )
        finally:
            close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
            if close is not None:
                try:
                    result = close()
                    if inspect.isawaitable(result):
                        async with asyncio.timeout(1):
                            await result
                except Exception:  # Cleanup must not mask the real failure/cancellation.
                    logger.debug("Unable to close structured stream alias=%s", alias)
    assert last_error is not None
    if last_validation_error is not None:
        raise last_validation_error from last_error
    raise last_error
