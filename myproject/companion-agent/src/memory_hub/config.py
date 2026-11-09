"""应用配置与启动校验（D §10.4、§10.7）。

校验失败即拒绝启动：两个应用共用 collection 或共用令牌环境变量，都会让隔离变成约定。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from memory_hub.scope import APP_PATTERN


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    name: str
    collection: str
    qdrant_token_env: str
    backend: str = "mem0"
    embedding: dict[str, Any] = field(default_factory=dict)


def from_mapping(raw: dict[str, Any]) -> list[AppConfig]:
    """解析 ``{"apps": {name: {...}}}`` 形状（与 config/memory.yaml 对应）。"""
    apps = raw.get("apps")
    if not isinstance(apps, dict) or not apps:
        raise ConfigError("memory config must define at least one app")
    out = []
    for name, body in apps.items():
        if not isinstance(body, dict):
            raise ConfigError(f"app {name!r} must be a mapping")
        out.append(AppConfig(
            name=name,
            collection=str(body.get("collection", "")),
            qdrant_token_env=str(body.get("qdrant_token_env", "")),
            backend=str(body.get("backend", "mem0")),
            embedding=dict(body.get("embedding", {})),
        ))
    validate_configs(out)
    return out


def validate_configs(configs: Iterable[AppConfig]) -> None:
    configs = list(configs)
    if not configs:
        raise ConfigError("no apps configured")
    names: set[str] = set()
    collections: set[str] = set()
    tokens: set[str] = set()
    for cfg in configs:
        if not APP_PATTERN.match(cfg.name):
            raise ConfigError(f"invalid app name: {cfg.name!r}")
        if cfg.name in names:
            raise ConfigError(f"duplicate app: {cfg.name}")
        if not cfg.collection:
            raise ConfigError(f"{cfg.name}: collection is required")
        if not cfg.qdrant_token_env:
            raise ConfigError(f"{cfg.name}: qdrant_token_env is required")
        if cfg.collection in collections:
            raise ConfigError(f"collection {cfg.collection!r} is shared by two apps")
        if cfg.qdrant_token_env in tokens:
            raise ConfigError(f"token {cfg.qdrant_token_env!r} is shared by two apps")
        names.add(cfg.name)
        collections.add(cfg.collection)
        tokens.add(cfg.qdrant_token_env)
