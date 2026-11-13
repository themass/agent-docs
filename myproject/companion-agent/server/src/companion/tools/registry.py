"""工具注册表：名称唯一；按产品与白名单过滤（T §2.8）。纯逻辑。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from companion.tools.spec import ToolSpec

Handler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class Registered:
    spec: ToolSpec
    handler: Handler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Registered] = {}

    def register(self, spec: ToolSpec, handler: Handler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"duplicate tool name: {spec.name}")
        self._tools[spec.name] = Registered(spec, handler)

    def get(self, name: str) -> Registered | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [r.spec for r in self._tools.values()]

    def for_product(self, product: str) -> list[ToolSpec]:
        return [s for s in self.specs() if product in s.products]
