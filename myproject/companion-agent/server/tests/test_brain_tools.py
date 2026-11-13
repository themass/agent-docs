"""工具经真实 DeerFlow 图的路由（P §2.2、T §2.3）。模型是脚本化的，不调用真实模型。

- 允许的自动工具：执行，文字回复正常交付；
- 需要确认的工具：只建确认记录，业务动作不执行；
- 白名单为空：工具调用被拒绝，业务动作不执行（fail closed）。
"""

from unittest.mock import AsyncMock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from companion.adapters.brain.deerflow import DeerFlowBrain, build_turn_graph
from companion.adapters.brain.tools import to_langchain_tools
from companion.app.tools.builtin import register_builtin_tools
from companion.app.tools.runtime import ToolRuntime
from companion.domain.tools.registry import ToolRegistry
from companion.ports.brain import TurnRequest


class ScriptedToolModel(BaseChatModel):
    script: list
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-tool"

    def bind_tools(self, tools, **kwargs):
        return self

    def _next(self):
        msg = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return msg

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._next())])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._next())])


class Store:
    def __init__(self):
        self.rows = {}

    async def create(self, rec):
        self.rows[rec.id] = rec

    async def get_pending(self, **kw):
        return None

    async def list_pending(self, **kw):
        return []

    async def decide(self, **kw):
        return True

    async def finish(self, **kw):
        return True

    async def expire_due(self, **kw):
        return 0


async def _run(script, product: str, allowed: set[str]):
    memory = AsyncMock()
    timeline = AsyncMock()
    registry = ToolRegistry()
    register_builtin_tools(registry, memory=memory, timeline=timeline)
    store = Store()
    runtime = ToolRuntime(registry=registry, confirmations=store)
    graph = build_turn_graph(ScriptedToolModel(script=list(script)),
                             tools=to_langchain_tools(registry.for_product(product)))
    brain = DeerFlowBrain(graph, tool_runtime=runtime, tool_allowed=frozenset(allowed), tool_product=product)
    turn = await brain.start_turn(TurnRequest(
        user_id="7", character_id="linche", message="请记住", system_prompt="你是陪伴者。",
        metadata={"session_id": 1, "locale": "zh-CN"}))
    text = "".join([chunk async for chunk in turn.tokens])
    return text, memory, timeline, store


async def test_allowed_auto_tool_runs_and_the_reply_is_delivered():
    script = [AIMessage(content="", tool_calls=[{"name": "remember_fact", "args": {"content": "我喜欢喝茶"}, "id": "c1"}]),
              AIMessage(content="好的，我记住了。")]
    text, memory, _timeline, _store = await _run(script, "chat", {"remember_fact"})
    assert memory.add.await_count == 1
    assert text == "好的，我记住了。"


async def test_confirm_tool_only_records_a_confirmation_and_does_not_execute():
    script = [AIMessage(content="", tool_calls=[{"name": "create_reminder",
                                                 "args": {"title": "吃药", "at": "2026-12-01T09:00:00+00:00"},
                                                 "id": "c2"}]),
              AIMessage(content="请确认是否提醒。")]
    text, _memory, timeline, store = await _run(script, "roleplay", {"create_reminder"})
    assert timeline.add.await_count == 0
    assert len(store.rows) == 1
    assert text == "请确认是否提醒。"


async def test_empty_allowance_denies_every_tool_call():
    script = [AIMessage(content="", tool_calls=[{"name": "remember_fact", "args": {"content": "x"}, "id": "c3"}]),
              AIMessage(content="好的")]
    _text, memory, _timeline, _store = await _run(script, "chat", set())
    assert memory.add.await_count == 0
