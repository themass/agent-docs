"""主脑适配（T4）：DeerFlow 图的流事件 → 领域事件。

替身按真实 LangGraph ``astream(stream_mode="messages")`` 的形状回放：每个元素是
``(message, metadata)``。工具调用块与正文块不混在一起（spike-results.md 的实测结论）。
"""

import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage

from companion.agent.brain.deerflow import DeerFlowBrain
from companion.agent.brain.fake import FakeBrain
from companion.agent.brain.port import TextDelta, ToolFinished, ToolStarted, TurnRequest


def request(**kw):
    base = dict(user_id="u1", character_id="linche", message="在吗")
    base.update(kw)
    return TurnRequest(**base)


async def collect(turn):
    return [chunk async for chunk in turn.tokens]


class StubGraph:
    """按 astream(stream_mode="messages") 的形状回放消息块。"""

    def __init__(self, items, *, raise_after=None):
        self._items = items
        self._raise_after = raise_after
        self.calls = []

    async def astream(self, inputs, *, context, stream_mode, **extra):
        self.calls.append((inputs, context, stream_mode, extra))
        for index, item in enumerate(self._items):
            if self._raise_after is not None and index >= self._raise_after:
                raise RuntimeError("model stream broke")
            yield item


async def test_every_graph_run_asks_for_exit_durability():
    """checkpoint 落盘策略必须是 exit。

    LangGraph 默认 ``async`` 每个图步骤写一次 checkpoint。生产库是跨地域的（实测往返 362ms），
    一个回合 25 次写 → 单是落盘就 10 秒（实测 9977ms → 714ms）。这条测试防的是有人
    把它改回默认值：那种改动不会让任何测试失败，只会让线上慢十几倍。
    """
    graph = StubGraph([text("在")])
    brain = DeerFlowBrain(graph, stateful=True)
    async for _ in brain.stream(messages=[], context={}, config={"configurable": {"thread_id": "s1"}}):
        pass
    assert graph.calls[0][3]["durability"] == "exit"


async def test_a_stateless_graph_gets_no_durability_hint():
    """没有 checkpointer 的图连 config 都没有，不该传 durability（参数对它是多余的）。"""
    graph = StubGraph([text("在")])
    brain = DeerFlowBrain(graph)
    async for _ in brain.stream(messages=[], context={}, config=None):
        pass
    assert graph.calls[0][3] == {}


def text(content):
    return (AIMessageChunk(content=content), {})


def tool_start(call_id, name):
    return (AIMessageChunk(content="", tool_call_chunks=[{"id": call_id, "name": name, "args": "", "index": 0}]), {})


def tool_result(call_id, name, content):
    return (ToolMessage(content=content, tool_call_id=call_id, name=name), {})


async def test_fake_brain_streams_and_records_request():
    brain = FakeBrain(["你好。", "我是林澈。"])
    turn = await brain.start_turn(request())
    assert await collect(turn) == ["你好。", "我是林澈。"]
    assert brain.requests[0].character_id == "linche"


async def test_fake_brain_cancel_stops_stream():
    brain = FakeBrain(["a", "b", "c"], delay=0.01)
    turn = await brain.start_turn(request())
    await turn.cancel_turn()
    assert await collect(turn) == []


async def test_stream_yields_text_deltas_in_order():
    graph = StubGraph([text("你"), text("好。")])
    events = [e async for e in DeerFlowBrain(graph).stream(messages=[], context={})]
    assert events == [TextDelta("你"), TextDelta("好。")]


async def test_tool_call_chunks_are_not_text_and_start_once():
    graph = StubGraph([tool_start("c1", "recall_facts"), tool_start("c1", "recall_facts"), text("好")])
    events = [e async for e in DeerFlowBrain(graph).stream(messages=[], context={})]
    assert events == [ToolStarted(call_id="c1", name="recall_facts"), TextDelta("好")]


async def test_tool_result_becomes_tool_finished():
    graph = StubGraph([tool_result("c1", "recall_facts", "喜欢茶")])
    events = [e async for e in DeerFlowBrain(graph).stream(messages=[], context={})]
    assert events == [ToolFinished(call_id="c1", name="recall_facts", content="喜欢茶")]


async def test_start_turn_passes_identity_and_prompt_in_context():
    graph = StubGraph([text("x")])
    await collect(await DeerFlowBrain(graph).start_turn(request(system_prompt="SYS")))
    _inputs, context, mode, _extra = graph.calls[0]
    assert mode == "messages"
    assert context["user_id"] == "u1"
    assert context["system_prompt"] == "SYS"
    assert context["turn_id"]


async def test_start_turn_cancel_stops_consumption():
    graph = StubGraph([text("x"), text("y")])
    turn = await DeerFlowBrain(graph).start_turn(request())
    await turn.cancel_turn()
    assert await collect(turn) == []


async def test_partial_text_is_delivered_before_a_stream_failure():
    graph = StubGraph([text("开始"), text("继续")], raise_after=1)
    turn = await DeerFlowBrain(graph).start_turn(request())
    received = []
    with pytest.raises(RuntimeError):
        async for chunk in turn.tokens:
            received.append(chunk)
    assert received == ["开始"]
