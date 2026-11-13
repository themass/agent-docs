"""应用配置与启动校验（D §10.4）。

记忆存在 MySQL（ca_memory_item）里，应用之间的隔离靠复合 user_id（``app:uid``，见 scope.py），
不需要每个应用各自的 collection 或令牌。这里只校验应用名合法且不重复。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from memory_hub.scope import APP_PATTERN

SUPPORTED_BACKENDS = frozenset({"mysql"})


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    name: str
    backend: str = "mysql"


def from_mapping(raw: dict[str, Any]) -> list[AppConfig]:
    """解析 ``{"apps": {name: {...}}}`` 形状。"""
    apps = raw.get("apps")
    if not isinstance(apps, dict) or not apps:
        raise ConfigError("memory config must define at least one app")
    out = []
    for name, body in apps.items():
        if not isinstance(body, dict):
            raise ConfigError(f"app {name!r} must be a mapping")
        out.append(AppConfig(name=name, backend=str(body.get("backend", "mysql"))))
    validate_configs(out)
    return out


def validate_configs(configs: Iterable[AppConfig]) -> None:
    configs = list(configs)
    if not configs:
        raise ConfigError("no apps configured")
    names: set[str] = set()
    for cfg in configs:
        if not APP_PATTERN.match(cfg.name):
            raise ConfigError(f"invalid app name: {cfg.name!r}")
        if cfg.name in names:
            raise ConfigError(f"duplicate app: {cfg.name}")
        if cfg.backend not in SUPPORTED_BACKENDS:
            raise ConfigError(f"{cfg.name}: unsupported backend {cfg.backend!r}")
        names.add(cfg.name)
