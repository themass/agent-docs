"""DeerFlow 大脑（P §2）。用 create_deerflow_agent 构图，对话历史保存在 checkpoint 里。

分工（chat-agent-next-plan.md §2.2）：
- 对话线程 = 会话（``thread_id_for(session_id)``）。模型每轮看到的历史来自 checkpoint，
  请求里只带本回合的新输入；摘要（``summary_text``）由 DeerFlow 的摘要中间件维护。
- 新输入用稳定 id（``lc_user_id(message_id)``）：合并后重跑时，同一条用户消息按 id 覆盖，不会重复。
- 本轮的提示词计划经 ``runtime.context`` 交给 ``PromptMiddleware``，图本身可以缓存复用。

``build_turn_graph``：一次性编译（进程内复用）。没有 checkpointer 时退回无状态（每轮只看本轮输入）。
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage

from companion.agent.brain.graph_middleware import (
    PromptMiddleware,
    SteerMiddleware,
    ToolAuditMiddleware,
    ToolAuthorizationMiddleware,
    ToolVisibilityMiddleware,
)
from companion.agent.brain.port import (
    BrainEvent,
    BrainTurn,
    GraphMessageIds,
    TextDelta,
    ToolFinished,
    ToolStarted,
    TurnRequest,
)
from companion.agent.brain.conversation import lc_user_id
from deerflow.agents.factory import create_deerflow_agent
from deerflow.agents.features import RuntimeFeatures

# 图编译时的占位提示词：真正的提示词由 PromptMiddleware 每轮写入（P §2.4）。
_PLACEHOLDER_SYSTEM = "You are a helpful assistant."

#: LangGraph 的 checkpoint 落盘策略。见 ``stream`` 里的说明。
DURABILITY = "exit"


def thread_id_for(session_id: int) -> str:
    return f"session-{session_id}"


def default_features(*, token_budget: bool = True, summarization: Any = False) -> RuntimeFeatures:
    """P §2.2 的开关表。沙箱、记忆、子 agent 一律关闭；摘要需要传入中间件实例才开启。"""
    return RuntimeFeatures(
        sandbox=False,
        memory=False,
        summarization=summarization,
        subagent=False,
        vision=False,
        auto_title=False,
        guardrail=False,
        loop_detection=True,
        token_budget=token_budget,
    )


def build_summarization(model: Any, *, trigger_tokens: int = 9000, keep_messages: int = 20) -> Any:
    """会话内的上下文压缩（chat-agent-context-design.md §3.2、§5）。

    超过 ``trigger_tokens`` 时，把较早的消息压成 ``summary_text``，保留最近 ``keep_messages`` 条原文；
    界面历史在消息表里，不受影响。
    """
    from deerflow.agents.middlewares.summarization_middleware import DeerFlowSummarizationMiddleware

    return DeerFlowSummarizationMiddleware(
        model=model, trigger=("tokens", trigger_tokens), keep=("messages", keep_messages))


def build_turn_graph(model: Any, tools: Sequence[Any] = (), *, name: str = "companion-turn",
                     features: RuntimeFeatures | None = None, checkpointer: Any = None,
                     summarization: Any = None, fallback_models: Sequence[Any] = ()):
    """``fallback_models``：主模型报错时依次尝试（LangChain 的模型降级中间件，按请求重新绑定工具）。"""
    extra: list[Any] = [
        PromptMiddleware(),
        ToolVisibilityMiddleware(),
        SteerMiddleware(),
        ToolAuditMiddleware(),
        ToolAuthorizationMiddleware(),
    ]
    if fallback_models:
        from langchain.agents.middleware import ModelFallbackMiddleware

        extra.append(ModelFallbackMiddleware(*fallback_models))
    return create_deerflow_agent(
        model,
        tools=list(tools),
        system_prompt=_PLACEHOLDER_SYSTEM,
        features=features or default_features(summarization=summarization or False),
        extra_middleware=extra,
        checkpointer=checkpointer,
        name=name,
    )


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _input_messages(request: TurnRequest) -> list[BaseMessage]:
    if request.inputs:
        return [HumanMessage(id=lc_user_id(i.message_id), content=i.text) for i in request.inputs]
    return [HumanMessage(content=request.message)]


class DeerFlowBrain:
    """tool_runtime 与 tool_allowed 由组合根注入：本回合允许的工具名，以及执行它们的运行时。
    两者都为空时，图内工具中间件会拒绝所有工具调用（fail closed）。"""

    def __init__(self, graph: Any, *, tool_runtime: Any = None, tool_allowed: frozenset[str] = frozenset(),
                 tool_product: str = "chat", stateful: bool = False) -> None:
        self._graph = graph
        self._tool_runtime = tool_runtime
        self._tool_allowed = tool_allowed
        self._tool_product = tool_product
        self._stateful = stateful   # 图是否带 checkpointer（决定是否按会话传 thread_id）

    async def stream(self, *, messages: list[BaseMessage], context: dict[str, Any],
                     config: dict[str, Any] | None = None) -> AsyncIterator[BrainEvent]:
        seen_calls: set[str] = set()
        seen_ids: set[str] = set()
        input_ids = {m.id for m in messages if m.id}
        kwargs: dict[str, Any] = {"context": context, "stream_mode": "messages"}
        if config is not None:   # 只有带 checkpoint 的图才按会话传线程
            kwargs["config"] = config
            # 每个图步骤都写一次 checkpoint 的默认策略（async）在这里代价极大：
            # LangGraph 默认按步骤写，一回合 25 次写，库往返几百毫秒时单是落盘就十秒起。
            # exit = 整个 run 结束时才写一次。前提是图里没有 interrupt()（我们没有：
            # 工具确认是回合之外的确认表，不靠图暂停），取消回合时状态仍会保留。
            kwargs["durability"] = DURABILITY
        async for msg, _meta in self._graph.astream({"messages": messages}, **kwargs):
            mid = getattr(msg, "id", None)
            if mid and mid not in seen_ids and mid not in input_ids and isinstance(msg, (AIMessage, ToolMessage)):
                seen_ids.add(mid)
                yield GraphMessageIds(ids=(mid,))
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

    def _context(self, request: TurnRequest, turn_id: str, steer_inbox: Any = None) -> dict[str, Any]:
        context: dict[str, Any] = {
            "system_prompt": request.system_prompt,
            "prompt_plan": request.prompt,
            "user_id": request.user_id,
            "turn_id": turn_id,
            "allowed_tools": self._tool_allowed,
        }
        if steer_inbox is not None:
            context["steer_inbox"] = steer_inbox
        if self._tool_runtime is not None:
            from companion.agent.tools.runtime import ToolTurn

            session_id = request.session_id or int(request.metadata.get("session_id", 0) or 0)
            context["tool_runtime"] = self._tool_runtime
            context["tool_turn"] = ToolTurn(
                owner_id=int(request.user_id) if request.user_id.isdigit() else 0,
                session_id=session_id,
                turn_id=turn_id,
                character_id=request.character_id,
                locale=str(request.metadata.get("locale", "zh-CN")),
                product=self._tool_product,
                allowed=self._tool_allowed,
            )
        return context

    def _config(self, request: TurnRequest) -> dict[str, Any] | None:
        if not self._stateful or request.session_id is None:
            return None
        return {"configurable": {"thread_id": thread_id_for(request.session_id)}}

    async def run(self, request: TurnRequest, steer_inbox: Any = None) -> AsyncIterator[BrainEvent]:
        """回合层用的入口：产出全部事件（文本、工具、写入线程的消息 id）。"""
        turn_id = str(request.metadata.get("turn_id") or uuid.uuid4().hex)
        config = self._config(request)
        collector = request.metadata.get("llm_collector")
        if collector is not None:
            # 无状态图（没有 checkpoint）也要挂回调，所以不能只在有 config 时才传
            config = {**(config or {}), "callbacks": [collector]}
        async for event in self.stream(messages=_input_messages(request),
                                       context=self._context(request, turn_id, steer_inbox),
                                       config=config):
            yield event

    async def start_turn(self, request: TurnRequest) -> BrainTurn:
        """BrainPort 兼容入口（语音等旧链路）：只产出文本增量。"""
        cancelled = asyncio.Event()
        turn_id = uuid.uuid4().hex

        async def tokens() -> AsyncIterator[str]:
            async for event in self.stream(messages=_input_messages(request),
                                           context=self._context(request, turn_id),
                                           config=self._config(request)):
                if cancelled.is_set():
                    return
                if isinstance(event, TextDelta):
                    yield event.text

        async def cancel() -> None:
            cancelled.set()

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=turn_id)

    async def aclose(self) -> None:
        return None
