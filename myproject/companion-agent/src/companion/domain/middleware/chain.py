"""中间件链：横切关注点显式化。

安全、记忆、抽取、授权这些如果散落在各处的业务代码里，迟早会漏一条——漏的时候
往往是在生产上，而且很难归因。这里固定成一条链、固定顺序，漏了就是 bug 而不是
设计选择。

顺序的道理：
- 安全必须最先，后面的任何环节都不该在未过安全的前提下运行；
- 记忆与抽取在安全之后、成本之前——它们会消耗预算；
- 成本最后，因为它要看到前面所有环节的用量。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class MiddlewareContext:
    """一次回合穿过中间件链时携带的东西。

    刻意做成可变对象：中间件要往里面塞东西（召回的记忆、抽取的事件、统计的
    用量），而每一环的产出都是下一环的输入。
    """

    user_id: str
    character_id: str
    message: str
    mode: str = "text"
    proactive: bool = False
    memory_block: str = ""
    recall_facts: list[Any] = field(default_factory=list)
    recall_events: list[Any] = field(default_factory=list)
    extracted_events: list[Any] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    denied_reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.denied_reason is None


class Middleware(Protocol):
    name: str

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any: ...


class MiddlewareChain:
    """按注册顺序执行。任一环拒绝就短路。"""

    def __init__(self, middlewares: list[Middleware]) -> None:
        self._middlewares = list(middlewares)

    @property
    def names(self) -> list[str]:
        return [m.name for m in self._middlewares]

    async def run(self, ctx: MiddlewareContext, terminal: Callable[[MiddlewareContext], Awaitable[Any]]) -> Any:
        async def call(index: int, current: MiddlewareContext) -> Any:
            if index >= len(self._middlewares):
                return await terminal(current)
            middleware = self._middlewares[index]
            return await middleware(current, lambda nxt: call(index + 1, nxt))

        return await call(0, ctx)
