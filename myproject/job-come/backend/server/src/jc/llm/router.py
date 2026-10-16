"""In-process LLM router with scenario-based failover (litellm SDK)."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

import yaml

from jc.config import settings

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    model: str
    api_base_env: str
    api_key_env: str
    timeout_sec: int
    temperature: float
    provider: str | None = None


class LLMRouter:
    def __init__(self, routing_path: Path) -> None:
        raw = yaml.safe_load(routing_path.read_text(encoding="utf-8"))
        defaults = raw.get("defaults", {})
        self._default_base_env = defaults.get("api_base_env", "JC_LLM_API_BASE")
        self._default_key_env = defaults.get("api_key_env", "JC_LLM_API_KEY")
        self._default_provider = defaults.get("provider")
        self._default_temperature = float(defaults.get("temperature", 0.1))

        self._providers: dict[str, tuple[str, str]] = {}
        for name, spec in (raw.get("providers") or {}).items():
            if not isinstance(spec, dict):
                continue
            self._providers[name] = (
                str(spec.get("api_base_env", self._default_base_env)),
                str(spec.get("api_key_env", self._default_key_env)),
            )

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
        )

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
    ) -> Any | T:
        import litellm

        chain = self._scenarios.get(scenario)
        if not chain:
            raise ValueError(f"Unknown LLM scenario: {scenario}")

        errors: list[str] = []
        for endpoint in chain:
            api_base, api_key = self._credentials(endpoint)
            if not api_key:
                errors.append(f"{endpoint.model}: missing {endpoint.api_key_env}")
                continue
            kwargs: dict[str, Any] = {
                "model": endpoint.model,
                "messages": messages,
                "api_base": api_base,
                "api_key": api_key,
                "temperature": temperature if temperature is not None else endpoint.temperature,
                "timeout": endpoint.timeout_sec,
                "drop_params": True,
            }
            try:
                from agentkit.common.trace import get_trace_id

                trace = get_trace_id()
            except Exception:  # noqa: BLE001
                trace = None
            if trace:
                kwargs["metadata"] = {"trace_id": trace, "scenario": scenario}
            if response_format is not None:
                kwargs["response_format"] = response_format
            if tools is not None:
                kwargs["tools"] = tools
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            try:
                response = await litellm.acompletion(**kwargs)
                if response_validator is not None:
                    return response_validator(response)
                return response
            except Exception as exc:  # noqa: BLE001
                # A 200 response can still be unusable (for example, blank or invalid JSON).
                # Treat validator failures like endpoint failures so the scenario can fail over.
                errors.append(f"{endpoint.model}: {type(exc).__name__}: {exc}")
                continue
        detail = "; ".join(errors) if errors else "no endpoints configured"
        raise RuntimeError(f"All models failed for scenario {scenario}: {detail}")

    async def astream_completion(
        self,
        scenario: str,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Any:
        """Return litellm async stream on first successful endpoint."""
        import litellm

        chain = self._scenarios.get(scenario)
        if not chain:
            raise ValueError(f"Unknown LLM scenario: {scenario}")

        errors: list[str] = []
        for endpoint in chain:
            api_base, api_key = self._credentials(endpoint)
            if not api_key:
                errors.append(f"{endpoint.model}: missing {endpoint.api_key_env}")
                continue
            kwargs: dict[str, Any] = {
                "model": endpoint.model,
                "messages": messages,
                "api_base": api_base,
                "api_key": api_key,
                "temperature": temperature if temperature is not None else endpoint.temperature,
                "timeout": endpoint.timeout_sec,
                "stream": True,
                "drop_params": True,
            }
            if tools is not None:
                kwargs["tools"] = tools
            try:
                from agentkit.common.trace import get_trace_id

                trace = get_trace_id()
            except Exception:  # noqa: BLE001
                trace = None
            if trace:
                kwargs["metadata"] = {"trace_id": trace, "scenario": scenario}
            try:
                return await litellm.acompletion(**kwargs)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{endpoint.model}: {exc}")
                continue
        detail = "; ".join(errors) if errors else "no endpoints configured"
        raise RuntimeError(f"All models failed for scenario {scenario}: {detail}")

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


def _server_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_dotenv_loaded() -> None:
    """Load backend/server/.env into os.environ so routing api_*_env vars resolve."""
    env_path = _server_root() / ".env"
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
        "OPENAI_API_BASE": settings.openai_api_base,
        "OPENAI_API_KEY": settings.openai_api_key,
    }
    value = mapping.get(env_name, "")
    return value or None


def _resolve_routing_path(raw: str) -> Path:
    path = Path(raw)
    if path.is_file():
        return path
    if not path.is_absolute():
        path = (_server_root() / path).resolve()
    return path


@lru_cache
def get_llm_router() -> LLMRouter:
    ensure_dotenv_loaded()
    server_root = _server_root()
    candidates = [
        _resolve_routing_path(settings.jc_llm_routing_path),
        server_root.parent / "agent" / "llm" / "routing.yaml",
        server_root.parent / "agent" / "llm" / "routing.example.yaml",
    ]
    for path in candidates:
        if path.is_file():
            return LLMRouter(path)
    raise FileNotFoundError(f"LLM routing config not found: {candidates[0]}")
