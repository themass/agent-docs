"""DeerFlow 大脑（P §2）。用 create_deerflow_agent 构图；每回合无状态，历史由调用方给出。

- build_turn_graph：一次性编译（进程内复用，图本身无状态；每轮的提示词、工具白名单、
  steer 收件箱都经 runtime.context 传入）。
- DeerFlowBrain.stream：把图的 messages 流翻译成 BrainEvent（文本增量、工具开始、工具结束）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, ToolMessage

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
    def __init__(self, graph: Any) -> None:
        self._graph = graph

    async def stream(self, *, messages: list[BaseMessage], context: dict[str, Any]) -> AsyncIterator[BrainEvent]:
        seen_calls: set[str] = set()
        async for msg, _meta in self._graph.astream({"messages": messages}, context=context, stream_mode="messages"):
            if isinstance(msg, ToolMessage):
                yield ToolFinished(call_id=msg.tool_call_id or "", name=msg.name or "", content=_text_of(msg.content))
                continue
            if not isinstance(msg, AIMessageChunk):
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
        }
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
