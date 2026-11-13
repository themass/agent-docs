"""DeerFlow 图 + Postgres checkpoint 的集成测试（chat-agent-next-plan.md 第 4 节的验证项）。

需要 COMPANION_TEST_PG_URL（例如 postgresql+psycopg://companion:companion@127.0.0.1:55432/companion_test）。
模型是脚本化的，会记下每次收到的消息，不调用真实模型。每个用例用随机会话 id。
"""

import os
import random

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from companion.brain.conversation_state import DeerFlowConversationState
from companion.brain.deerflow import DeerFlowBrain, build_summarization, build_turn_graph
from companion.domain.prompt.plan import DepthInjection, PromptPlan
from companion.brain.port import TextDelta, TurnInputMessage, TurnRequest

PG_URL = os.environ.get("COMPANION_TEST_PG_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="COMPANION_TEST_PG_URL not set")


def _conninfo() -> str:
    return "postgresql://" + PG_URL.split("://", 1)[1]


class RecordingModel(BaseChatModel):
    replies: list = []
    seen: list = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "recording"

    def bind_tools(self, tools, **kwargs):
        return self

    def _reply(self, messages):
        self.seen.append(list(messages))
        text = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._reply(messages)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._reply(messages)


@pytest.fixture
async def saver():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(_conninfo(), open=False, min_size=1, max_size=4,
                               kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
    await pool.open()
    cp = AsyncPostgresSaver(pool)
    await cp.setup()
    yield cp
    await pool.close()


def _session() -> int:
    return random.randint(10**9, 10**10)


def _brain(model, saver, **kw):
    graph = build_turn_graph(model, checkpointer=saver, **kw)
    return DeerFlowBrain(graph, stateful=True), graph


async def _turn(brain, session_id, inputs, plan=None, inbox=None):
    req = TurnRequest(user_id="1", character_id="r", message="", session_id=session_id,
                      inputs=tuple(TurnInputMessage(mid, text) for mid, text in inputs), prompt=plan)
    return "".join([e.text async for e in brain.run(req, inbox) if isinstance(e, TextDelta)])


def _conversation(messages):
    """模型收到的非系统消息：(类型, id, 内容)。"""
    return [(type(m).__name__, m.id, m.content) for m in messages if not isinstance(m, SystemMessage)]


async def test_second_turn_sees_the_first_turn_from_the_checkpoint(saver):
    model = RecordingModel(replies=["你好小明", "你叫小明"])
    brain, _ = _brain(model, saver)
    sid = _session()
    await _turn(brain, sid, [(1, "我叫小明")])
    assert await _turn(brain, sid, [(2, "我叫什么？")]) == "你叫小明"
    conv = _conversation(model.seen[-1])
    humans = [(i, c) for t, i, c in conv if t == "HumanMessage" and i in ("m1", "m2")]
    assert humans == [("m1", "我叫小明"), ("m2", "我叫什么？")]
    assert any(t == "AIMessage" and c == "你好小明" for t, _, c in conv)


async def test_rerun_with_the_same_ids_does_not_duplicate_input(saver):
    model = RecordingModel(replies=["回复"])
    brain, graph = _brain(model, saver)
    sid = _session()
    req = TurnRequest(user_id="1", character_id="r", message="", session_id=sid,
                      inputs=(TurnInputMessage(10, "第一句"),))
    stream = brain.run(req)
    async for _ in stream:     # 模拟合并：首个事件就中止
        break
    await stream.aclose()
    await _turn(brain, sid, [(10, "第一句"), (11, "第二句")])
    ids = await DeerFlowConversationState(graph).present_ids(session_id=sid)
    assert ids.count("m10") == 1 and "m11" in ids


async def test_conversation_state_edits_what_the_model_sees(saver):
    model = RecordingModel(replies=["好的"])
    brain, graph = _brain(model, saver)
    state = DeerFlowConversationState(graph)
    sid = _session()
    await _turn(brain, sid, [(1, "秘密是 42")])
    await _turn(brain, sid, [(2, "改我")])
    assert await state.remove(session_id=sid, ids=["m1"]) == 1
    assert await state.replace_user_text(session_id=sid, lc_id="m2", text="已改")
    await state.append_assistant(session_id=sid, lc_id="a99", text="说到一半（回复被中断）")
    await _turn(brain, sid, [(3, "继续")])
    contents = [c for _, _, c in _conversation(model.seen[-1])]
    assert "秘密是 42" not in contents and "已改" in contents and "说到一半（回复被中断）" in contents
    assert "m1" not in await state.present_ids(session_id=sid)


async def test_a_second_instance_continues_the_same_thread(saver):
    """两个独立的图实例（模拟两台服务器）共用 Postgres：第二个接得上第一个的上下文。"""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    sid = _session()
    first, _ = _brain(RecordingModel(replies=["记住了"]), saver)
    await _turn(first, sid, [(1, "我喜欢猫")])

    pool = AsyncConnectionPool(_conninfo(), open=False, min_size=1, max_size=2,
                               kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row})
    await pool.open()
    try:
        model = RecordingModel(replies=["你喜欢猫"])
        second, _ = _brain(model, AsyncPostgresSaver(pool))
        await _turn(second, sid, [(2, "我喜欢什么？")])
        assert ("HumanMessage", "m1", "我喜欢猫") in _conversation(model.seen[-1])
    finally:
        await pool.close()


async def test_summarization_compacts_old_messages_and_feeds_the_summary_back(saver):
    model = RecordingModel(replies=["嗯" * 40])
    summarizer = RecordingModel(replies=["SUMMARY: 用户聊了很多事"])
    brain, graph = _brain(model, saver, summarization=build_summarization(summarizer, trigger_tokens=60,
                                                                         keep_messages=2))
    sid = _session()
    for i in range(1, 6):
        await _turn(brain, sid, [(i, "说点什么" * 10)])
    state = DeerFlowConversationState(graph)
    assert "SUMMARY" in await state.summary(session_id=sid)
    assert "m1" not in await state.present_ids(session_id=sid)
    assert any("SUMMARY" in str(m.content) for m in model.seen[-1])


async def test_steered_messages_are_stored_with_stable_ids(saver):
    class Inbox:
        def __init__(self):
            self.items = [("77", "顺便问一下")]

        def take_all(self):
            items, self.items = self.items, []
            return items

    model = RecordingModel(replies=["好"])
    brain, graph = _brain(model, saver)
    sid = _session()
    await _turn(brain, sid, [(1, "开始")], inbox=Inbox())
    assert "m77" in await DeerFlowConversationState(graph).present_ids(session_id=sid)


async def test_depth_injections_reach_the_model_but_not_the_checkpoint(saver):
    model = RecordingModel(replies=["收到"])
    brain, graph = _brain(model, saver)
    sid = _session()
    plan = PromptPlan(system="角色设定 SYS", injections=(DepthInjection(0, "system", "历史后指令 PHI"),))
    await _turn(brain, sid, [(1, "你好")], plan=plan)
    seen = model.seen[-1]
    assert any(isinstance(m, SystemMessage) and "角色设定 SYS" in m.content for m in seen)
    assert isinstance(seen[-1], HumanMessage) and "历史后指令 PHI" in seen[-1].content
    snapshot = await graph.aget_state({"configurable": {"thread_id": f"session-{sid}"}})
    assert all("PHI" not in str(m.content) for m in snapshot.values["messages"])
