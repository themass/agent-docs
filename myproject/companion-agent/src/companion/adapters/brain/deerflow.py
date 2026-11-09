"""DeerFlow 大脑（P §2）。用 create_deerflow_agent 构图；每回合无状态，历史由调用方给出。

- build_turn_graph：一次性编译（进程内复用，图本身无状态；每轮的提示词、工具白名单、
  steer 收件箱都经 runtime.context 传入）。
- DeerFlowBrain.stream：把图的 messages 流翻译成 BrainEvent（文本增量、工具开始、工具结束）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage

from companion.ports.brain import BrainEvent, BrainTurn, TextDelta, ToolFinished, ToolStarted, TurnRequest
from companion.adapters.brain.graph_middleware import (
    PromptMiddleware,
    SteerMiddleware,
    ToolAuditMiddleware,
    ToolAuthorizationMiddleware,
    ToolVisibilityMiddleware,
)
from deerflow.agents.factory import create_deerflow_agent
from deerflow.agents.features import RuntimeFeatures

# 图编译时的占位提示词：真正的提示词由 PromptMiddleware 每轮写入（P §2.4）。
_PLACEHOLDER_SYSTEM = "You are a helpful assistant."


def default_features(*, token_budget: bool = True) -> RuntimeFeatures:
    """P §2.2 的开关表。沙箱、记忆、摘要、子 agent 一律关闭。"""
    return RuntimeFeatures(
        sandbox=False,
        memory=False,
        summarization=False,
        subagent=False,
        vision=False,
        auto_title=False,
        guardrail=False,
        loop_detection=True,
        token_budget=token_budget,
    )


def build_turn_graph(model: Any, tools: Sequence[Any] = (), *, name: str = "companion-turn",
                     features: RuntimeFeatures | None = None):
    return create_deerflow_agent(
        model,
        tools=list(tools),
        system_prompt=_PLACEHOLDER_SYSTEM,
        features=features or default_features(),
        extra_middleware=[
            PromptMiddleware(),
            ToolVisibilityMiddleware(),
            SteerMiddleware(),
            ToolAuditMiddleware(),
            ToolAuthorizationMiddleware(),
        ],
        name=name,
    )


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


class DeerFlowBrain:
    """tool_runtime 与 tool_allowed 由组合根注入：本回合允许的工具名，以及执行它们的运行时。
    两者都为空时，图内工具中间件会拒绝所有工具调用（fail closed）。"""

    def __init__(self, graph: Any, *, tool_runtime: Any = None, tool_allowed: frozenset[str] = frozenset(),
                 tool_product: str = "chat") -> None:
        self._graph = graph
        self._tool_runtime = tool_runtime
        self._tool_allowed = tool_allowed
        self._tool_product = tool_product

    async def stream(self, *, messages: list[BaseMessage], context: dict[str, Any]) -> AsyncIterator[BrainEvent]:
        seen_calls: set[str] = set()
        async for msg, _meta in self._graph.astream({"messages": messages}, context=context, stream_mode="messages"):
            if isinstance(msg, ToolMessage):
                yield ToolFinished(call_id=msg.tool_call_id or "", name=msg.name or "", content=_text_of(msg.content))
                continue
            if not isinstance(msg, (AIMessageChunk, AIMessage)):
                continue
            # 非流式的完整回复（AIMessage）：模型没有逐 token 输出时，正文整段到达，也要交付。
            if isinstance(msg, AIMessage) and not isinstance(msg, AIMessageChunk):
                if getattr(msg, "tool_calls", None):
                    for call in msg.tool_calls:
                        cid = call.get("id") or ""
                        if cid and cid not in seen_calls:
                            seen_calls.add(cid)
                            yield ToolStarted(call_id=cid, name=call.get("name") or "")
                    continue
                text = _text_of(msg.content)
                if text:
                    yield TextDelta(text=text)
                continue
            if msg.tool_call_chunks:
                for chunk in msg.tool_call_chunks:
                    cid = chunk.get("id")
                    if cid and cid not in seen_calls:
                        seen_calls.add(cid)
                        yield ToolStarted(call_id=cid, name=chunk.get("name") or "")
                continue  # 工具调用块不含正文（已验证，docs/implementation/spike-results.md）
            text = _text_of(msg.content)
            if text:
                yield TextDelta(text=text)


    async def start_turn(self, request: TurnRequest) -> BrainTurn:
        """BrainPort 兼容入口：只产出文本增量（工具事件由 stream() 的调用方消费）。"""
        import uuid

        cancelled = asyncio.Event()
        turn_id = uuid.uuid4().hex
        context: dict[str, Any] = {
            "system_prompt": request.system_prompt,
            "user_id": request.user_id,
            "turn_id": turn_id,
            "allowed_tools": self._tool_allowed,
        }
        if self._tool_runtime is not None:
            from companion.app.tools.runtime import ToolTurn

            context["tool_runtime"] = self._tool_runtime
            context["tool_turn"] = ToolTurn(
                owner_id=int(request.user_id) if request.user_id.isdigit() else 0,
                session_id=int(request.metadata.get("session_id", 0) or 0),
                turn_id=turn_id,
                character_id=request.character_id,
                locale=str(request.metadata.get("locale", "zh-CN")),
                product=self._tool_product,
                allowed=self._tool_allowed,
            )
        messages: list[BaseMessage] = [HumanMessage(content=request.message)]

        async def tokens() -> AsyncIterator[str]:
            async for event in self.stream(messages=messages, context=context):
                if cancelled.is_set():
                    return
                if isinstance(event, TextDelta):
                    yield event.text

        async def cancel() -> None:
            cancelled.set()

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=turn_id)
