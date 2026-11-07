"""模型路由：读取 routing.yaml，把场景解析为有序的模型链。

只做配置解析，不发起调用。调用与故障转移在后续实现中加入。
密钥与网关地址只通过环境变量名引用，本模块不读取密钥值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    model: str
    provider: str
    api_base_env: str
    api_key_env: str
    timeout_sec: int
    temperature: float
    max_tokens: int
    reasoning_effort: str | None = None
    extra_body: dict[str, Any] | None = field(default=None)


class LLMRouter:
    def __init__(self, routing_path: Path) -> None:
        raw = yaml.safe_load(routing_path.read_text(encoding="utf-8")) or {}
        defaults = raw.get("defaults") or {}
        self._default_provider = str(defaults.get("provider", "gateway"))
        self._default_base_env = str(defaults.get("api_base_env", "COMPANION_LLM_API_BASE"))
        self._default_key_env = str(defaults.get("api_key_env", "COMPANION_LLM_API_KEY"))
        self._default_temperature = float(defaults.get("temperature", 0.7))
        self._default_max_tokens = int(defaults.get("max_tokens", 4096))
        if self._default_max_tokens <= 0:
            raise ValueError("defaults.max_tokens must be positive")

        self._providers: dict[str, tuple[str, str]] = {}
        for name, spec in (raw.get("providers") or {}).items():
            if isinstance(spec, dict):
                self._providers[name] = (
                    str(spec.get("api_base_env", self._default_base_env)),
                    str(spec.get("api_key_env", self._default_key_env)),
                )

        self._scenarios: dict[str, list[ModelEndpoint]] = {}
        for scenario, entries in (raw.get("scenarios") or {}).items():
            if not entries:
                raise ValueError(f"scenario {scenario!r} has no models")
            self._scenarios[scenario] = [self._endpoint(e, scenario) for e in entries]

    def _endpoint(self, entry: dict[str, Any], scenario: str) -> ModelEndpoint:
        if "model" not in entry:
            raise ValueError(f"scenario {scenario!r}: entry without model")
        provider = str(entry.get("provider") or self._default_provider)
        prov_base, prov_key = self._providers.get(
            provider, (self._default_base_env, self._default_key_env)
        )
        return ModelEndpoint(
            model=str(entry["model"]),
            provider=provider,
            api_base_env=str(entry.get("api_base_env") or prov_base),
            api_key_env=str(entry.get("api_key_env") or prov_key),
            timeout_sec=int(entry.get("timeout_sec", 60)),
            temperature=float(entry.get("temperature", self._default_temperature)),
            max_tokens=int(entry.get("max_tokens", self._default_max_tokens)),
            reasoning_effort=entry.get("reasoning_effort"),
            extra_body=entry.get("extra_body"),
        )

    def chain(self, scenario: str) -> list[ModelEndpoint]:
        """返回场景的模型链（按故障转移顺序）。未知场景抛 KeyError。"""
        return list(self._scenarios[scenario])

    @property
    def scenarios(self) -> list[str]:
        return sorted(self._scenarios)
