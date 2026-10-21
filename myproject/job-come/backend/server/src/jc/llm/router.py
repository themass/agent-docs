"""In-process LLM router with scenario-based failover (litellm SDK)."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TypeVar

import yaml

from jc.config import settings
from jc.llm.call_log import LLMLogContext
from jc.paths import SERVER_ROOT, agent_file, resolve_under_server

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    model: str
    api_base_env: str
    api_key_env: str
    timeout_sec: int
    temperature: float
    provider: str | None = None
    # Explicitly scoped per-scenario reasoning policy. ``none`` is meaningful
    # and must not be treated as a missing value: ingestion should produce
    # schema JSON, not spend its whole budget in hidden reasoning.
    reasoning_effort: str | None = None
    max_tokens: int | None = None
    extra_body: dict[str, Any] | None = None


class LLMRouter:
    def __init__(self, routing_path: Path) -> None:
        raw = yaml.safe_load(routing_path.read_text(encoding="utf-8"))
        defaults = raw.get("defaults", {})
        self._default_base_env = defaults.get("api_base_env", "JC_LLM_API_BASE")
        self._default_key_env = defaults.get("api_key_env", "JC_LLM_API_KEY")
        self._default_provider = defaults.get("provider")
        self._default_temperature = float(defaults.get("temperature", 0.1))
        self._default_max_tokens = int(defaults.get("max_tokens", 100_000))
        if self._default_max_tokens <= 0:
            raise ValueError("defaults.max_tokens must be positive")

        self._providers: dict[str, tuple[str, str]] = {}
        for name, spec in (raw.get("providers") or {}).items():
            if not isinstance(spec, dict):
                continue
            self._providers[name] = (
                str(spec.get("api_base_env", self._default_base_env)),
                str(spec.get("api_key_env", self._default_key_env)),
            )

        # Gateway prices for models litellm's bundled map does not know (see
        # `jc.llm.pricing`). Read here because `routing.yaml` is already the one
        # place a model is named, so the price cannot drift from the name.
        from jc.llm.pricing import parse_pricing

        self._pricing = parse_pricing(raw.get("pricing"))

        self._scenarios: dict[str, list[ModelEndpoint]] = {}
        for name, entries in raw.get("scenarios", {}).items():
            self._scenarios[name] = [
                self._endpoint_from_entry(entry) for entry in entries
            ]

    def _endpoint_from_entry(self, entry: dict[str, Any]) -> ModelEndpoint:
        provider_name = entry.get("provider") or self._default_provider
        base_env = entry.get("api_base_env")
        key_env = entry.get("api_key_env")
        if provider_name and provider_name in self._providers:
            prov_base, prov_key = self._providers[provider_name]
            base_env = base_env or prov_base
            key_env = key_env or prov_key
        return ModelEndpoint(
            model=entry["model"],
            api_base_env=str(base_env or self._default_base_env),
            api_key_env=str(key_env or self._default_key_env),
            timeout_sec=int(entry.get("timeout_sec", 120)),
            temperature=float(entry.get("temperature", self._default_temperature)),
            provider=str(provider_name) if provider_name else None,
            reasoning_effort=(
                str(entry["reasoning_effort"])
                if "reasoning_effort" in entry and entry["reasoning_effort"] is not None
                else None
            ),
            max_tokens=self._output_limit(entry),
            extra_body=(
                dict(entry["extra_body"])
                if isinstance(entry.get("extra_body"), dict)
                else None
            ),
        )

    def _output_limit(self, entry: dict[str, Any]) -> int:
        limit = int(entry.get("max_tokens", self._default_max_tokens))
        if limit <= 0:
            raise ValueError("endpoint.max_tokens must be positive")
        return limit

    def price_for_model(self, model: str | None) -> Any:
        """Configured price for a served model name, or `None` if unpriced.

        Accepts either spelling (`openai/gpt-6-1-sol` as written in the config, or
        the bare `gpt-6-1-sol` the gateway echoes back in the response).
        """
        from jc.llm.pricing import price_for

        return price_for(self._pricing, model)

    def chain_for(self, scenario: str) -> list[ModelEndpoint]:
        """Resolved failover chain for a scenario.

        Public because the DeerFlow adapter (`jc.llm.chat_litellm`) needs the same
        chain the deterministic services use. That shared read is the whole point:
        `routing.yaml` stays the one place a model is named, instead of the agent
        harness carrying a second, silently diverging copy.
        """
        chain = self._scenarios.get(scenario)
        if not chain:
            raise ValueError(f"Unknown LLM scenario: {scenario}")
        return list(chain)

    def credentials_for(self, endpoint: ModelEndpoint) -> tuple[str | None, str | None]:
        """Public alias of `_credentials` for the DeerFlow adapter."""
        return self._credentials(endpoint)

    def _credentials(self, endpoint: ModelEndpoint) -> tuple[str | None, str | None]:
        api_base = _resolve_env(endpoint.api_base_env)
        api_key = _resolve_env(endpoint.api_key_env)
        return api_base, api_key

    async def acompletion(
        self,
        scenario: str,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_validator: Callable[[Any], T] | None = None,
        log_context: LLMLogContext | None = None,
        timeout_seconds: float | None = None,
        buffered_stream: bool = False,
        stream_attempt_timeout_seconds: float | None = None,
    ) -> Any | T:
        """Call a scenario's chain, failing over until one endpoint answers.

        The chain walk is `litellm.Router`'s, not this method's: see
        `jc.llm.transport`. What is left here is JC's own contract -
        With `buffered_stream`, receive deltas internally but return only a fully
        assembled and validated response. `timeout_seconds` then limits connection/
        read idle time; `stream_attempt_timeout_seconds` additionally bounds each
        complete streaming attempt. The caller owns the total chain deadline.

        `response_validator` receives the whole response and may reject it, and
        a rejection has to behave like an endpoint failure so the chain moves
        on. That is arranged by running the validator *inside* litellm's call
        stack through `validation_scope`.
        """
        from jc.llm import audit_hook
        from jc.llm.transport import (
            has_validated,
            router_for,
            take_validated,
            validation_scope,
        )

        if stream_attempt_timeout_seconds is not None and (
            not buffered_stream or stream_attempt_timeout_seconds <= 0
        ):
            raise ValueError(
                "stream attempt timeout requires buffered_stream and a positive budget"
            )
        caller = (log_context or LLMLogContext(caller="unknown")).caller
        transport = router_for(scenario)
        kwargs = self._request_kwargs(
            transport.primary,
            messages=messages,
            tools=tools,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            scenario=scenario,
            caller=caller,
        )
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be positive")
            kwargs["timeout"] = timeout_seconds
        router = transport.router

        validator = _text_validator(response_validator)
        async with audit_hook.llm_call_scope(
            scenario, caller, "router", stream=buffered_stream
        ) as scope:
            audit_hook.report_skipped(transport.skipped)
            audit_hook.report_prompt(messages, trace_id=_current_trace_id())
            scope.trace_id = scope.trace_id or _current_trace_id()
            started = time.monotonic()
            if buffered_stream:
                from jc.llm.buffered_stream import collect_completion

                response, validated = await collect_completion(
                    transport, kwargs, response_validator,
                    attempt_timeout_seconds=stream_attempt_timeout_seconds,
                )
                validated_ran = response_validator is not None
            else:
                with validation_scope(validator):
                    response = await router.acompletion(**kwargs)
                    validated = take_validated()
                    validated_ran = has_validated()
            audit_hook.report_success(response, latency_ms=_elapsed_ms(started))
        if response_validator is None:
            return response
        # Normally the validator already ran inside the call and its result is
        # reused rather than recomputed - a caller's parse is not idempotent in
        # general. But litellm only applies post-call rules to a response it
        # recognises, so a shape it skips would otherwise return None here and
        # fail at the caller's first subscript. Running it now keeps the
        # contract "a validator's return value, or an exception" unconditional.
        return validated if validated_ran else response_validator(response)

    async def astream_completion(
        self,
        scenario: str,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        log_context: LLMLogContext | None = None,
    ) -> Any:
        """Open a stream on the first endpoint that accepts it.

        The audit row is written when the stream *opens*, not when it finishes:
        the caller owns the iterator, so there is no point here at which token
        usage or the final text is known.
        """
        from jc.llm import audit_hook
        from jc.llm.transport import router_for

        caller = (log_context or LLMLogContext(caller="unknown")).caller
        transport = router_for(scenario)
        kwargs = self._request_kwargs(
            transport.primary,
            messages=messages,
            tools=tools,
            response_format=None,
            temperature=temperature,
            max_tokens=None,
            scenario=scenario,
            caller=caller,
        )
        kwargs["stream"] = True
        router = transport.router

        async with audit_hook.llm_call_scope(
            scenario, caller, "router", stream=True
        ) as scope:
            audit_hook.report_skipped(transport.skipped)
            audit_hook.report_prompt(messages, trace_id=_current_trace_id())
            scope.trace_id = scope.trace_id or _current_trace_id()
            stream = await router.acompletion(**kwargs)
            audit_hook.report_stream_opened(stream)
        return stream

    def _request_kwargs(
        self,
        alias: str,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        response_format: dict[str, Any] | None,
        temperature: float | None,
        max_tokens: int | None,
        scenario: str,
        caller: str,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": alias,
            "messages": messages,
            "drop_params": True,
            # Read back by the audit callback, which otherwise cannot tell which
            # scenario or code path a raw litellm call belongs to.
            "metadata": {
                "scenario": scenario,
                "caller": caller,
                "channel": "router",
                "trace_id": _current_trace_id(),
            },
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools is not None:
            kwargs["tools"] = tools
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return kwargs

    def content_from_response(self, response: Any) -> str:
        """Extract textual content from LiteLLM/OpenAI-compatible response shapes.

        Providers occasionally return content blocks or an incomplete response while still
        returning HTTP 200.  This helper deliberately returns an empty string for those
        malformed shapes; JSON-task validators convert that into a controlled retry.
        """
        choices = _field(response, "choices")
        if not isinstance(choices, (list, tuple)) or not choices:
            return ""
        message = _field(choices[0], "message")
        if message is None:
            return ""
        return _content_to_text(_field(message, "content"))


def _text_validator(
    response_validator: Callable[[Any], Any] | None,
) -> Callable[[str], Any] | None:
    """Adapt a response-shaped validator to the text-only rule signature.

    Callers validate the whole response because that is what they receive, but
    litellm's `post_call_rules` only passes the assistant text. Wrapping the
    text back into the minimal response shape keeps the existing call sites
    unchanged while letting the verdict be reached early enough to fail over.
    """
    if response_validator is None:
        return None

    def validate(text: str) -> T:
        return response_validator(
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
            )
        )

    return validate


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _current_trace_id() -> str | None:
    try:
        from agentkit.common.trace import get_trace_id

        return get_trace_id()
    except Exception:  # noqa: BLE001
        return None


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        return text if isinstance(text, str) else ""
    if isinstance(content, (list, tuple)):
        return "".join(_content_to_text(part) for part in content)
    text = _field(content, "text")
    return text if isinstance(text, str) else ""


def ensure_dotenv_loaded() -> None:
    """Load backend/server/.env into os.environ so routing api_*_env vars resolve."""
    env_path = SERVER_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _resolve_env(env_name: str) -> str | None:
    ensure_dotenv_loaded()
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    return _env_from_settings(env_name)


def _env_from_settings(env_name: str) -> str | None:
    text_base = settings.jc_llm_api_base
    text_key = settings.jc_llm_api_key
    vision_base = settings.jc_llm_vision_api_base or text_base
    vision_key = settings.jc_llm_vision_api_key or text_key
    mapping = {
        "JC_LLM_API_BASE": text_base,
        "JC_LLM_API_KEY": text_key,
        "JC_LLM_VISION_API_BASE": vision_base,
        "JC_LLM_VISION_API_KEY": vision_key,
    }
    value = mapping.get(env_name, "")
    return value or None


def _resolve_routing_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_file():
        return path
    return resolve_under_server(path)


@lru_cache
def get_llm_router() -> LLMRouter:
    ensure_dotenv_loaded()
    candidates = [
        _resolve_routing_path(settings.jc_llm_routing_path),
        agent_file("llm", "routing.yaml"),
        agent_file("llm", "routing.example.yaml"),
    ]
    for path in candidates:
        if path.is_file():
            return LLMRouter(path)
    raise FileNotFoundError(f"LLM routing config not found: {candidates[0]}")
