"""图内中间件（T §1、P §2.4）。全部只实现异步钩子，并显式声明锚点。

回合上下文通过 runtime.context（TurnRuntimeContext，Mapping）读取，不走全局变量。
"""

from __future__ import annotations

import json
import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command

from companion.prompt.plan import splice_injections
from companion.turn.steer import render_steer_block
from companion.turn.conversation import lc_user_id

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


def _injection_message(role: str, text: str, *, system_as_user: bool):
    """对话中间的注入。严格的后端（千问、vLLM、Anthropic）拒绝不在开头的 system 消息，
    所以默认把 system 角色的注入写成带标记的用户消息。"""
    if role == "assistant":
        return AIMessage(content=text)
    if role == "system" and not system_as_user:
        return SystemMessage(content=text)
    body = f"<system_note>\n{text}\n</system_note>" if role == "system" else text
    return HumanMessage(content=body, additional_kwargs={"hide_from_ui": True})


@Prev(SystemMessageCoalescingMiddleware)
class PromptMiddleware(AgentMiddleware):
    """每次模型调用都由我们决定提示词（P §2.4）：

    - 系统提示词写进 ``request.system_message``（图可缓存，提示词每轮重算）；
    - 提示词计划里的按深度注入（角色备注、世界书、作者注、历史后指令）插进本次请求的消息列表，
      **只进请求，不写回对话线程**。
    """

    async def awrap_model_call(self, request, handler):
        ctx = _ctx(request.runtime.context if request.runtime else None)
        plan = ctx.get("prompt_plan")
        prompt = plan.system if plan is not None else ctx.get("system_prompt")
        if prompt:
            request = request.override(system_message=SystemMessage(content=prompt))
        if plan is not None and plan.injections:
            system_as_user = bool(ctx.get("system_injection_as_user", True))
            messages = splice_injections(
                list(request.messages), plan.injections,
                lambda role, text: _injection_message(role, text, system_as_user=system_as_user))
            request = request.override(messages=messages)
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
        # 每条插话一条消息，id 用消息表主键：之后删除或编辑这条插话时能精确找到它。
        return {"messages": [HumanMessage(id=lc_user_id(int(mid)), content=render_steer_block([(mid, text)]))
                             for mid, text in items]}


@Prev(ToolErrorHandlingMiddleware)
class ToolAuditMiddleware(AgentMiddleware):
    """工具审计的位置占位。

    审计在 ``ToolRuntime`` 内完成（它知道最终状态与参数指纹，T §2.5），这里不再重复写，
    避免同一次调用落两条记录。中间件保留是为了锚点顺序与将来的耗时指标。
    """

    async def awrap_tool_call(self, request, handler):
        return await handler(request)


@Next(ToolAuditMiddleware)
class ToolAuthorizationMiddleware(AgentMiddleware):
    """工具调用的唯一执行入口（T §2.3）。

    模型只能看到白名单工具（ToolVisibilityMiddleware），这里再校验一次：白名单、参数、权限。
    执行交给 ``ToolRuntime``，不调用 DeerFlow 传入的工具协程。
    没有回合上下文时直接拒绝（fail closed）。
    """

    async def awrap_tool_call(self, request, handler):
        name = request.tool_call.get("name", "")
        call_id = request.tool_call.get("id", "")
        args = dict(request.tool_call.get("args") or {})
        ctx = _ctx(request.runtime.context if request.runtime else None)
        turn = ctx.get("tool_turn")
        runtime = ctx.get("tool_runtime")
        if turn is None or runtime is None:
            return ToolMessage(
                content=json.dumps({"error": "tool_not_available", "tool": name}, ensure_ascii=False),
                tool_call_id=call_id, name=name, status="error",
            )
        outcome = await runtime.invoke(turn, name, args)
        ok = outcome.status in ("executed", "needs_confirmation")
        return ToolMessage(content=outcome.model_text, tool_call_id=call_id, name=name,
                           status="success" if ok else "error")
