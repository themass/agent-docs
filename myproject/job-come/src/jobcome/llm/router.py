"""In-process LLM router with scenario-based failover (litellm SDK)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from jobcome.config import settings


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    model: str
    api_base_env: str
    api_key_env: str
    timeout_sec: int
    temperature: float


class LLMRouter:
    def __init__(self, routing_path: Path) -> None:
        raw = yaml.safe_load(routing_path.read_text(encoding="utf-8"))
        defaults = raw.get("defaults", {})
        self._default_base_env = defaults.get("api_base_env", "YUAI_API_BASE")
        self._default_key_env = defaults.get("api_key_env", "YUAI_API_KEY")
        self._default_temperature = float(defaults.get("temperature", 0.1))
        self._scenarios: dict[str, list[ModelEndpoint]] = {}
        for name, entries in raw.get("scenarios", {}).items():
            self._scenarios[name] = [
                ModelEndpoint(
                    model=entry["model"],
                    api_base_env=entry.get("api_base_env", self._default_base_env),
                    api_key_env=entry.get("api_key_env", self._default_key_env),
                    timeout_sec=int(entry.get("timeout_sec", 120)),
                    temperature=float(entry.get("temperature", self._default_temperature)),
                )
                for entry in entries
            ]

    async def acompletion(
        self,
        scenario: str,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        import litellm

        chain = self._scenarios.get(scenario)
        if not chain:
            raise ValueError(f"Unknown LLM scenario: {scenario}")

        last_error: Exception | None = None
        for endpoint in chain:
            api_base = os.environ.get(endpoint.api_base_env) or _env_from_settings(
                endpoint.api_base_env
            )
            api_key = os.environ.get(endpoint.api_key_env) or _env_from_settings(
                endpoint.api_key_env
            )
            if not api_key:
                last_error = RuntimeError(f"Missing API key env: {endpoint.api_key_env}")
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
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            try:
                return await litellm.acompletion(**kwargs)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
        raise RuntimeError(f"All models failed for scenario {scenario}: {last_error}")

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

        last_error: Exception | None = None
        for endpoint in chain:
            api_base = os.environ.get(endpoint.api_base_env) or _env_from_settings(
                endpoint.api_base_env
            )
            api_key = os.environ.get(endpoint.api_key_env) or _env_from_settings(
                endpoint.api_key_env
            )
            if not api_key:
                last_error = RuntimeError(f"Missing API key env: {endpoint.api_key_env}")
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
                last_error = exc
                continue
        raise RuntimeError(f"All models failed for scenario {scenario}: {last_error}")

    def content_from_response(self, response: Any) -> str:
        return response.choices[0].message.content or ""


def _env_from_settings(env_name: str) -> str | None:
    mapping = {
        "YUAI_API_BASE": settings.yuai_api_base,
        "YUAI_API_KEY": settings.yuai_api_key,
        "YUAI_VISION_API_BASE": settings.yuai_vision_api_base,
        "YUAI_VISION_API_KEY": settings.yuai_vision_api_key,
        "OPENAI_API_BASE": settings.openai_api_base,
        "OPENAI_API_KEY": settings.openai_api_key,
    }
    value = mapping.get(env_name, "")
    return value or None


@lru_cache
def get_llm_router() -> LLMRouter:
    candidates = [
        Path(settings.job_come_llm_routing_path),
        Path(__file__).resolve().parents[3] / "deploy" / "llm" / "routing.yaml",
        Path(__file__).resolve().parents[3] / "deploy" / "llm" / "routing.example.yaml",
    ]
    for path in candidates:
        if path.is_file():
            return LLMRouter(path)
    raise FileNotFoundError(f"LLM routing config not found: {candidates[0]}")
