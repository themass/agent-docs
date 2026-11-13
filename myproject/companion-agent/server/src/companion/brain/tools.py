"""把 ToolSpec 翻译成 DeerFlow（LangChain）可识别的工具声明（T §2.8）。

这里的协程只用于让模型看到工具的名字、描述与参数 Schema。真正的执行发生在
ToolAuthorizationMiddleware 里：它先校验白名单与权限，再调用 ToolRuntime。
如果这个协程被直接调用，说明绕过了中间件，直接报错。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from langchain_core.tools import StructuredTool

from companion.tools.spec import ToolSpec


def to_langchain_tools(specs: Iterable[ToolSpec]) -> list[Any]:
    tools: list[Any] = []
    for spec in specs:
        tools.append(StructuredTool.from_function(
            coroutine=_declared_only(spec.name),
            name=spec.name,
            description=spec.description,
            args_schema=spec.params,
        ))
    return tools


def _declared_only(name: str):
    async def _refuse(**_kwargs: Any) -> str:
        raise RuntimeError(f"tool {name} must run through the authorization middleware")

    return _refuse
