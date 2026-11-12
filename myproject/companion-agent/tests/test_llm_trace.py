"""LlmCallCollector：用 LangChain 自带的假聊天模型真实触发回调，不手工构造事件。"""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from companion.adapters.brain.llm_trace import MAX_MESSAGE_CHARS, LlmCallCollector


def _model(*messages):
    return GenericFakeChatModel(messages=iter(messages))


async def test_a_call_records_input_output_usage_and_finish_reason():
    reply = AIMessage(content="先歇一会儿", usage_metadata={"input_tokens": 120, "output_tokens": 18, "total_tokens": 138,
                                                          "input_token_details": {"cache_read": 100}},
                      response_metadata={"finish_reason": "stop", "model_name": "fake-1"})
    collector = LlmCallCollector()
    await _model(reply).ainvoke([SystemMessage(content="你是林澈"), HumanMessage(content="今天好累")],
                                config={"callbacks": [collector]})

    (call,) = collector.drain()
    assert [m["role"] for m in call.input_messages] == ["system", "human"]
    assert call.input_messages[1]["content"] == "今天好累"
    assert call.output_text == "先歇一会儿"
    assert (call.input_tokens, call.output_tokens, call.cached_tokens) == (120, 18, 100)
    assert (call.finish_reason, call.model) == ("stop", "fake-1")
    assert call.total_ms is not None and call.total_ms >= 0


async def test_streaming_records_time_to_first_token():
    collector = LlmCallCollector()
    chunks = [c async for c in _model(AIMessage(content="一二三")).astream(
        [HumanMessage(content="数数")], config={"callbacks": [collector]})]
    assert chunks
    (call,) = collector.drain()
    assert call.first_token_ms is not None and call.first_token_ms <= call.total_ms


async def test_several_calls_in_one_turn_are_ordered():
    collector = LlmCallCollector()
    model = _model(AIMessage(content="第一次"), AIMessage(content="第二次"))
    await model.ainvoke([HumanMessage(content="a")], config={"callbacks": [collector]})
    await model.ainvoke([HumanMessage(content="b")], config={"callbacks": [collector]})
    assert [(c.seq, c.output_text) for c in collector.drain()] == [(0, "第一次"), (1, "第二次")]


async def test_drain_empties_the_collector():
    collector = LlmCallCollector()
    await _model(AIMessage(content="x")).ainvoke([HumanMessage(content="y")], config={"callbacks": [collector]})
    assert len(collector.drain()) == 1 and collector.drain() == []


async def test_a_failing_call_is_recorded_with_its_error_type():
    class Boom(GenericFakeChatModel):
        def _generate(self, *a, **k):
            raise TimeoutError("gateway")

    collector = LlmCallCollector()
    try:
        await Boom(messages=iter([])).ainvoke([HumanMessage(content="hi")], config={"callbacks": [collector]})
    except TimeoutError:
        pass
    (call,) = collector.drain()
    assert call.error_code == "TimeoutError" and call.output_text == ""


async def test_reasoning_is_taken_from_additional_kwargs_or_content_blocks():
    a = AIMessage(content="答", additional_kwargs={"reasoning_content": "先想一下"})
    b = AIMessage(content=[{"type": "thinking", "thinking": "再想想"}, {"type": "text", "text": "答"}])
    c1, c2 = LlmCallCollector(), LlmCallCollector()
    await _model(a).ainvoke([HumanMessage(content="q")], config={"callbacks": [c1]})
    await _model(b).ainvoke([HumanMessage(content="q")], config={"callbacks": [c2]})
    assert c1.drain()[0].reasoning_text == "先想一下"
    assert c2.drain()[0].reasoning_text == "再想想"


async def test_very_long_prompts_are_clipped_not_stored_whole():
    collector = LlmCallCollector()
    await _model(AIMessage(content="x")).ainvoke(
        [SystemMessage(content="词" * (MAX_MESSAGE_CHARS + 500))], config={"callbacks": [collector]})
    stored = collector.drain()[0].input_messages[0]["content"]
    assert len(stored) < MAX_MESSAGE_CHARS + 60 and "截断" in stored


from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class StreamingModel(BaseChatModel):
    """像真实供应商那样流式输出：正文分几块，用量和结束原因放在最后一块上。"""

    pieces: list[str] = ["先歇", "一会儿"]
    usage: dict = {"input_tokens": 50, "output_tokens": 6, "total_tokens": 56}

    @property
    def _llm_type(self) -> str:
        return "streaming-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="".join(self.pieces)))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        for i, piece in enumerate(self.pieces):
            last = i == len(self.pieces) - 1
            chunk = AIMessageChunk(content=piece,
                                   usage_metadata=self.usage if last else None,
                                   response_metadata={"finish_reason": "stop", "model_name": "stream-1"} if last else {})
            if run_manager:
                run_manager.on_llm_new_token(piece, chunk=ChatGenerationChunk(message=chunk))
            yield ChatGenerationChunk(message=chunk)


async def test_streamed_usage_and_finish_reason_reach_the_collector():
    collector = LlmCallCollector()
    chunks = [c async for c in StreamingModel().astream([HumanMessage(content="hi")], config={"callbacks": [collector]})]
    assert chunks     # 块数随 LangChain 版本不同（新版会多一个空的收尾块），不是要验证的东西
    (call,) = collector.drain()
    assert call.output_text == "先歇一会儿"
    assert (call.input_tokens, call.output_tokens, call.finish_reason, call.model) == (50, 6, "stop", "stream-1")
    assert call.first_token_ms is not None


async def test_requested_tool_calls_are_recorded_with_name_and_arguments():
    reply = AIMessage(content="", tool_calls=[{"id": "call_1", "name": "add_event", "args": {"title": "面试"}}])
    collector = LlmCallCollector()
    await _model(reply).ainvoke([HumanMessage(content="周五面试")], config={"callbacks": [collector]})
    (call,) = collector.drain()
    assert call.tool_calls == [{"id": "call_1", "name": "add_event", "args": {"title": "面试"}}]
    assert call.output_text == ""            # 只请求了工具、没有正文：这一行是“调用了工具”的唯一证据


async def test_tool_results_in_the_next_input_keep_which_call_they_answer():
    from langchain_core.messages import ToolMessage

    asked = AIMessage(content="", tool_calls=[{"id": "call_1", "name": "add_event", "args": {}}])
    collector = LlmCallCollector()
    await _model(AIMessage(content="好的")).ainvoke(
        [HumanMessage(content="周五面试"), asked, ToolMessage(content="已添加", tool_call_id="call_1", name="add_event")],
        config={"callbacks": [collector]})
    items = collector.drain()[0].input_messages
    assert items[1]["tool_calls"] == [{"id": "call_1", "name": "add_event"}]
    assert (items[2]["role"], items[2]["tool_call_id"], items[2]["name"], items[2]["content"]) == (
        "tool", "call_1", "add_event", "已添加")
