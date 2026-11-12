"""记忆中心：按应用绑定作用域（D §10.3）。

每个应用拿到的是一个 ``ScopedMemory``：它只把 ``app:uid`` 交给底层端口，因此一个应用的
调用无法触达另一个应用的数据。``kinds`` 过滤是普通的元数据过滤——失效只会让召回不准，
不会跨用户泄露（D §10.7）。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from memory_hub.config import AppConfig, validate_configs
from memory_hub.scope import compose_user_id


class UnknownApp(KeyError):
    pass


class ScopedMemory:
    """作用域客户端：方法签名与 companion.ports.memory.MemoryPort 完全一致（规范 §3）。

    外部传入的 user_id 永远是应用内用户 id；这里统一加上 ``app:`` 前缀后交给后端。
    kinds 原样透传给后端（不在这里做事后过滤），保证每个后端的结果一致。
    """

    def __init__(self, *, app: str, port: Any) -> None:
        self._app = app
        self._port = port

    @property
    def app(self) -> str:
        return self._app

    def _uid(self, user_id: str) -> str:
        return compose_user_id(self._app, user_id)

    async def add(self, user_id: str, items: Sequence[Any]) -> list[Any]:
        return await self._port.add(self._uid(user_id), items)

    async def search(self, user_id: str, query: str, limit: int = 5,
                     kinds: Iterable[Any] | None = None) -> list[Any]:
        return await self._port.search(self._uid(user_id), query, limit=limit, kinds=kinds)

    async def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0,
                            include_history: bool = False) -> list[Any]:
        return await self._port.list_for_user(self._uid(user_id), limit=limit, offset=offset,
                                              include_history=include_history)

    async def supersede(self, user_id: str, old_id: str, item: Any) -> Any | None:
        return await self._port.supersede(self._uid(user_id), old_id, item)

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        return await self._port.delete_one(self._uid(user_id), memory_id)

    async def delete_user(self, user_id: str) -> int:
        return await self._port.delete_user(self._uid(user_id))


class MemoryHub:
    def __init__(self, configs: Iterable[AppConfig], ports: dict[str, Any]) -> None:
        configs = list(configs)
        validate_configs(configs)
        missing = {c.name for c in configs} - set(ports)
        if missing:
            raise ValueError(f"no backend port for apps: {sorted(missing)}")
        self._configs = {c.name: c for c in configs}
        self._ports = dict(ports)

    @classmethod
    def from_config(cls, configs: Iterable[AppConfig],
                    build_port: Callable[[AppConfig], Any]) -> "MemoryHub":
        """每个应用由 ``build_port`` 构造自己的端口（自己的 collection、自己的令牌）。"""
        configs = list(configs)
        validate_configs(configs)
        return cls(configs, {c.name: build_port(c) for c in configs})

    def apps(self) -> list[str]:
        return sorted(self._configs)

    def for_app(self, app: str) -> ScopedMemory:
        if app not in self._ports:
            raise UnknownApp(app)
        return ScopedMemory(app=app, port=self._ports[app])
