import asyncio

import pytest

from companion.brain import FakeBrain
from companion.brain.deerflow import BrainUnavailable, DeerFlowBrain, _ai_text_delta, _thread_id_for
from companion.brain.port import TurnRequest


def request(**kw):
    base = dict(user_id="u1", character_id="xiaowu", message="在吗")
    base.update(kw)
    return TurnRequest(**base)


async def collect(turn):
    return [chunk async for chunk in turn.tokens]


async def test_fake_brain_streams_and_records_request():
    brain = FakeBrain(["你好。", "我是晓雾。"])
    turn = await brain.start_turn(request())
    assert await collect(turn) == ["你好。", "我是晓雾。"]
    assert brain.requests[0].character_id == "xiaowu"


async def test_fake_brain_cancel_stops_stream():
    brain = FakeBrain(["a", "b", "c"], delay=0.01)
    turn = await brain.start_turn(request())
    await turn.cancel_turn()
    assert await collect(turn) == []


class Ev:
    """Stand-in for deerflow.client.StreamEvent (its module pulls heavy deps)."""

    def __init__(self, type, data=None):
        self.type = type
        self.data = data or {}


def ai(text):
    return Ev("messages-tuple", {"type": "ai", "content": text})


def tool(name="search"):
    return Ev("messages-tuple", {"type": "tool", "content": "结果", "name": name})


def values():
    return Ev("values", {"messages": []})


class StubDeerFlow:
    """按真实 DeerFlowClient 的形状回放事件。

    真实客户端的 stream() 是**同步生成器**，签名是 (message, *, thread_id)。
    这个替身保持同样的形状，否则测出来的东西和线上不是一回事。
    """

    def __init__(self, events, *, raise_after=None):
        self._events = events
        self._raise_after = raise_after
        self.calls = []

    def stream(self, message, *, thread_id=None):
        self.calls.append((message, thread_id))
        for index, event in enumerate(self._events):
            if self._raise_after is not None and index >= self._raise_after:
                raise RuntimeError("boom")
            yield event


async def test_deerflow_brain_passes_through_only_ai_text_deltas():
    client = StubDeerFlow([values(), tool(), ai("你"), ai("好。"), ai("")])
    turn = await DeerFlowBrain(client).start_turn(request())
    assert await collect(turn) == ["你", "好。"]


async def test_deerflow_brain_uses_a_stable_thread_per_user_and_character():
    """线程 id 必须是稳定的：随机 id 会让每次进房都丢掉历史。"""
    client = StubDeerFlow([ai("x")])
    await collect(await DeerFlowBrain(client).start_turn(request()))
    assert client.calls[0][1] == "u1:xiaowu"


async def test_deerflow_brain_reuses_explicit_thread_id():
    client = StubDeerFlow([ai("x")])
    await collect(await DeerFlowBrain(client).start_turn(request(thread_id="thr-existing")))
    assert client.calls[0][1] == "thr-existing"


async def test_deerflow_brain_delivers_partial_output_when_stream_raises():
    """主脑中途崩了，已经产出的内容照样交付。"""
    client = StubDeerFlow([ai("开始"), ai("继续")], raise_after=2)
    turn = await DeerFlowBrain(client).start_turn(request())
    assert await collect(turn) == ["开始", "继续"]


async def test_deerflow_brain_cancel_stops_consumption():
    client = StubDeerFlow([ai("x"), ai("y")])
    turn = await DeerFlowBrain(client).start_turn(request())
    await turn.cancel_turn()
    assert await collect(turn) == []


def test_deerflow_brain_requires_client():
    with pytest.raises(BrainUnavailable):
        DeerFlowBrain(None)


def test_ai_text_delta_ignores_non_text_events():
    assert _ai_text_delta(Ev("values", {"messages": []})) == ""
    assert _ai_text_delta(Ev("messages-tuple", {"type": "tool", "content": "x"})) == ""
    assert _ai_text_delta(Ev("messages-tuple", {"type": "ai", "content": None})) == ""
    assert _ai_text_delta(Ev("messages-tuple", {"type": "ai", "content": "好"})) == "好"


def test_thread_id_is_stable_and_scoped():
    assert _thread_id_for(request()) == "u1:xiaowu"
    assert _thread_id_for(request(user_id="u2")) == "u2:xiaowu"
