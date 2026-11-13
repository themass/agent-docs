"""模型路由：读取 routing.yaml，把场景解析为有序的模型链。

只做配置解析，不发起调用。调用与故障转移在后续实现中加入。
密钥与网关地址只通过环境变量名引用，本模块不读取密钥值。

换模型不用改 yaml：每个场景对应一个 ``.env`` 变量，逗号分隔、按顺序故障转移::

    COMPANION_LLM_MODEL_COMPANION_CHAT=openai/gpt-6-luna,openai/glm-5.3-flash

yaml 只保留每个位置的调优（超时、推理强度、extra_body 等），那些值是对网关实测出来的，
换模型不该重填。变量未设置或为空 = 用 yaml 里提交的模型名，所以没有 .env 的检出照样能跑。
拼错场景名（变量设了却没有对应场景）直接报错，而不是静默继续跑旧模型。
与 job-come 的 ``JC_LLM_MODEL_*`` 是同一套约定。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

#: 场景模型链的环境变量前缀。``COMPANION_LLM_MODEL_<SCENARIO>``，场景名大写。
MODEL_OVERRIDE_ENV_PREFIX = "COMPANION_LLM_MODEL_"


def _model_override_env(scenario: str) -> str:
    return f"{MODEL_OVERRIDE_ENV_PREFIX}{scenario.upper()}"


def _reject_unknown_model_overrides(declared: list[str], environ: dict[str, str]) -> None:
    """``COMPANION_LLM_MODEL_*`` 指向一个 yaml 里不存在的场景 → 报错。

    不报错的话：变量设了、人以为换了模型，实际还在跑旧模型，而且没有任何地方提示。
    """
    known = {_model_override_env(name) for name in declared}
    for key in environ:
        if key.startswith(MODEL_OVERRIDE_ENV_PREFIX) and key not in known:
            raise ValueError(
                f"{key} 没有对应的场景（routing.yaml 里的场景："
                f"{sorted(declared)}）。检查变量名是否拼错"
            )


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


def _override_chain(raw: str) -> list[str]:
    """``a,b`` → ``["a", "b"]``。去掉空白与空项；未设置或全空返回 []。"""
    return [name.strip() for name in raw.split(",") if name.strip()]


def _apply_override(chain: list[ModelEndpoint], names: list[str]) -> list[ModelEndpoint]:
    """用环境变量里的模型名替换链上的模型，**按位置对齐**，每一跳的调优沿用 yaml 对应位置。

    链比 yaml 长时，多出来的跳数沿用最后一条 yaml 的调优（同一个策略，不是随便给默认值）。
    链比 yaml 短时，多出来的 yaml 位置直接丢弃——那是有意的：变量就是新的完整链。
    """
    out: list[ModelEndpoint] = []
    for i, name in enumerate(names):
        policy = chain[min(i, len(chain) - 1)]
        out.append(replace(policy, model=name))
    return out


class LLMRouter:
    def __init__(self, routing_path: Path, environ: dict[str, str] | None = None) -> None:
        """``environ`` 默认是进程环境（.env 已经在启动脚本里导出）；测试可以传入一份假的。"""
        env = dict(os.environ) if environ is None else dict(environ)
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

        declared = list((raw.get("scenarios") or {}).keys())
        _reject_unknown_model_overrides(declared, env)

        self._scenarios: dict[str, list[ModelEndpoint]] = {}
        for scenario, entries in (raw.get("scenarios") or {}).items():
            if not entries:
                raise ValueError(f"scenario {scenario!r} has no models")
            chain = [self._endpoint(e, scenario) for e in entries]
            override = _override_chain(env.get(_model_override_env(scenario), ""))
            if override:
                chain = _apply_override(chain, override)
            self._scenarios[scenario] = chain

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
