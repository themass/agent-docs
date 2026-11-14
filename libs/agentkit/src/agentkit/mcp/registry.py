from __future__ import annotations
from typing import Any, Callable, Coroutine
ToolHandler = Callable[..., Coroutine[Any, Any, Any]]

class McpToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}

    def tool(self, name: str):
        def decorator(fn: ToolHandler) -> ToolHandler:
            self._tools[name] = fn
            return fn
        return decorator

    def names(self) -> list[str]:
        return sorted(self._tools.keys())
