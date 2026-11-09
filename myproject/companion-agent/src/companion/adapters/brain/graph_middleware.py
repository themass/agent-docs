"""图内中间件（T §1、P §2.4）。全部只实现异步钩子，并显式声明锚点。

回合上下文通过 runtime.context（TurnRuntimeContext，Mapping）读取，不走全局变量。
"""

from __future__ import annotations

import json
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from companion.domain.turn.steer import render_steer_block

# DeerFlow 的锚点装饰器（deerflow/agents/features.py）。锚点名必须与 factory 中的类一致。
from deerflow.agents.features import Next, Prev
from deerflow.agents.middlewares.system_message_coalescing_middleware import SystemMessageCoalescingMiddleware
from deerflow.agents.middlewares.tool_error_handling_middleware import ToolErrorHandlingMiddleware

ASK_CLARIFICATION = "ask_clarification"


def _ctx(obj: Any) -> dict[str, Any]:
    """runtime.context 是 TypedDict（Mapping）。缺失时返回空字典，不抛错。"""
    if obj is None:
        return {}
    return dict(obj) if hasattr(obj, "keys") else {}


@Prev(SystemMessageCoalescingMiddleware)
class PromptMiddleware(AgentMiddleware):
    """每回合的系统提示词写进 request.system_message（图可缓存，提示词每轮重算，P §2.4）。"""

    async def awrap_model_call(self, request, handler):
        prompt = _ctx(request.runtime.context if request.runtime else None).get("system_prompt")
        if prompt:
            request = request.override(system_message=SystemMessage(content=prompt))
        return await handler(request)


@Next(PromptMiddleware)
class ToolVisibilityMiddleware(AgentMiddleware):
    """模型只看到本回合白名单里的工具；DeerFlow 强制加入的 ask_clarification 永远过滤掉（P §2.2）。"""

    async def awrap_model_call(self, request, handler):
        allowed = _ctx(request.runtime.context if request.runtime else None).get("allowed_tools")
        tools = []
        for tool in request.tools:
            name = getattr(tool, "name", None) or (tool.get("name") if isinstance(tool, dict) else None)
            if name == ASK_CLARIFICATION:
                continue
            if allowed is not None and name not in allowed:
                continue
            tools.append(tool)
        return await handler(request.override(tools=tools))


@Next(ToolVisibilityMiddleware)
class SteerMiddleware(AgentMiddleware):
    """在下一次模型调用之前注入排队的插话（D §6.4）。只实现异步钩子。"""

    async def abefore_model(self, state, runtime):
        ctx = _ctx(runtime.context)
        inbox = ctx.get("steer_inbox")
        if inbox is None:
            return None
        items = inbox.take_all()
        if not items:
            return None
        emit = ctx.get("events")
        if emit is not None:
            await emit({"type": "steered", "message_ids": [mid for mid, _ in items]})
        return {"messages": [HumanMessage(content=render_steer_block(items))]}


@Prev(ToolErrorHandlingMiddleware)
class ToolAuditMiddleware(AgentMiddleware):
    """记录每次工具调用（状态、耗时）。参数只记指纹，不记原文（O §4.1、T §2.5）。"""

    async def awrap_tool_call(self, request, handler):
        started = time.monotonic()
        name = request.tool_call.get("name", "")
        status = "executed"
        try:
            result = await handler(request)
            return result
        except Exception:
            status = "failed"
            raise
        finally:
            emit = _ctx(request.runtime.context if request.runtime else None).get("audit")
            if emit is not None:
                await emit({"tool": name, "status": status,
                            "latency_ms": int((time.monotonic() - started) * 1000)})


@Next(ToolAuditMiddleware)
class ToolAuthorizationMiddleware(AgentMiddleware):
    """工具调用的最后一道关：不在白名单里的调用直接拒绝，不执行（T §2.3）。"""

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call.get("name", "")
        call_id = request.tool_call.get("id", "")
        allowed = _ctx(request.runtime.context if request.runtime else None).get("allowed_tools")
        if allowed is not None and name not in allowed:
            return ToolMessage(
                content=json.dumps({"error": "tool_not_available", "tool": name}, ensure_ascii=False),
                tool_call_id=call_id, name=name, status="error",
            )
        return await handler(request)
