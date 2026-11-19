"""回合接口与管线的集成测试。

不需要 fastapi 也能跑的部分（管线、取消）走纯逻辑；HTTP 层在装了 fastapi 的
环境里额外覆盖，没装就跳过——这个包的核心不该被 web 栈绑死。
"""

import asyncio

import pytest

from companion.agent.brain.fake import FakeBrain
from companion.agent.brain.port import BrainTurn, TurnRequest
from companion.service.turn.pipeline import TurnPipeline


async def drain(pipeline, request):
    return [out async for out in pipeline.run(request)]


def req(message="在吗"):
    return TurnRequest(user_id="u1", character_id="linche", message=message)


async def test_pipeline_emits_one_sentence_at_a_time():
    brain = FakeBrain(["我最近。", "有点卡住。"])
    out = await drain(TurnPipeline(brain), req())
    assert [o.text for o in out] == ["我最近。", "有点卡住。"]


async def test_pipeline_keeps_one_line_cue_json_whole():
    """生产日志里 `said='{"say":"…` 泄漏的回归测试：一行 cue JSON 无论怎么分块
    都必须整段进 ingest——say 变成人话，cues 变成意图，`{"say":` 绝不进朗读文本。"""
    line = '{"say":"好，那先把能跑的部分跑起来。你现在卡在哪？","cues":[{"kind":"avatar.expression","name":"calm","anchor":"segment_start"}]}'
    chunks = [line[i:i + 9] for i in range(0, len(line), 9)]
    brain = FakeBrain(chunks)
    out = await drain(TurnPipeline(brain), req())
    assert [o.text for o in out] == ["好，那先把能跑的部分跑起来。你现在卡在哪？"]
    assert out[0].source == "structured"
    assert [i.name for i in out[0].intents] == ["calm"]


async def test_pipeline_text_then_json_order():
    brain = FakeBrain(["你把报错贴给我。", '{"say":"好。","cues":[]}'])
    out = await drain(TurnPipeline(brain), req())
    assert [o.text for o in out] == ["你把报错贴给我。", "好。"]


async def test_pipeline_strips_emotion_tags_and_emits_events():
    brain = FakeBrain(["[joy]你来了。今天怎么样？"])
    sink: list[str] = []
    out = await drain(TurnPipeline(brain, event_sink=sink.append), req())
    assert out[0].text == "你来了。"
    assert any('"type": "emotion"' in s for s in sink)
    assert any("joy" in s for s in sink)


class _ExplodingBrain:
    async def start_turn(self, request):
        async def tokens():
            yield "第一句。"
            raise RuntimeError("boom")

        async def cancel():
            return None

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id="t1")

    async def aclose(self):
        return None


async def test_pipeline_delivers_partial_output_when_brain_fails():
    # 语音场景里让已生成的话作废，比吞掉异常更糟。
    out = await drain(TurnPipeline(_ExplodingBrain()), req())
    assert [o.text for o in out] == ["第一句。"]


class _SlowBrain:
    """吐第一句后卡住，用来验证打断。"""

    def __init__(self):
        self.cancelled = False

    async def start_turn(self, request):
        async def tokens():
            yield "第一句。"
            await asyncio.sleep(5)
            yield "不该出现。"

        async def cancel():
            self.cancelled = True

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id="t1")

    async def aclose(self):
        return None


@pytest.mark.parametrize("partial", ['{"say":"unfinished', '{"say":"' + "x" * 4100])
async def test_cancelled_json_turn_does_not_poison_next_turn(partial):
    class Brain:
        def __init__(self):
            self.calls = 0
            self.blocked = asyncio.Event()

        async def start_turn(self, request):
            self.calls += 1
            first = self.calls == 1

            async def tokens():
                if first:
                    yield partial
                    self.blocked.set()
                    await asyncio.Event().wait()
                else:
                    yield '{"say":"下一轮正常。","cues":[]}'

            async def cancel():
                return None

            return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=str(self.calls))

    brain = Brain()
    pipeline = TurnPipeline(brain)
    task = asyncio.create_task(drain(pipeline, req()))
    await asyncio.wait_for(brain.blocked.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    out = await drain(pipeline, req())
    assert [o.text for o in out] == ["下一轮正常。"]


async def test_cancelled_prose_is_discarded_before_next_turn():
    class Brain:
        def __init__(self):
            self.calls = 0
            self.blocked = asyncio.Event()
            self.cancelled = []

        async def start_turn(self, request):
            self.calls += 1
            turn_id = str(self.calls)

            async def tokens():
                if turn_id == "1":
                    yield "[joy]cancelled buffer"
                    self.blocked.set()
                    await asyncio.Event().wait()
                else:
                    yield "Next turn."

            async def cancel():
                self.cancelled.append(turn_id)

            return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=turn_id)

    brain = Brain()
    events = []
    emitted = []
    pipeline = TurnPipeline(brain, event_sink=events.append)

    async def consume():
        async for output in pipeline.run(req()):
            emitted.append(output.text)

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(brain.blocked.wait(), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert emitted == []
    assert events == []
    assert brain.cancelled == ["1"]
    assert pipeline.turn_id == ""
    out = await drain(pipeline, req())
    assert [o.text for o in out] == ["Next turn."]
    assert events == []


async def test_aclose_discards_buffer_and_allows_next_turn():
    class Brain:
        def __init__(self):
            self.calls = 0
            self.cancelled = []

        async def start_turn(self, request):
            self.calls += 1
            turn_id = str(self.calls)

            async def tokens():
                if turn_id == "1":
                    # feed() buffers the tail before run() yields the first sentence.
                    yield "First. [joy]cancelled buffer"
                else:
                    yield '{"say":"Next turn.","cues":[]}'

            async def cancel():
                self.cancelled.append(turn_id)

            return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=turn_id)

    brain = Brain()
    events = []
    pipeline = TurnPipeline(brain, event_sink=events.append)
    stream = pipeline.run(req())
    try:
        first = await stream.__anext__()
        assert first.text == "First."
    finally:
        await stream.aclose()
    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()
    assert brain.cancelled == ["1"]
    assert pipeline.turn_id == ""
    assert events == []
    out = await drain(pipeline, req())
    assert [o.text for o in out] == ["Next turn."]
    assert out[0].source == "structured"
    assert events == []


async def test_pipeline_cancel_reaches_brain():
    brain = _SlowBrain()
    pipeline = TurnPipeline(brain)
    stream = pipeline.run(req())
    first = await stream.__anext__()
    assert first.text == "第一句。"
    await pipeline.cancel()
    assert brain.cancelled is True


def test_app_requires_livekit_for_sessions():
    """没配 LiveKit 时建会话要明确报错，而不是发一个空 token 出去。"""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from companion.bootstrap.app import create_app

    client = TestClient(create_app(livekit_url=""))
    response = client.post("/v1/voice/sessions", json={"character_id": "linche"})
    assert response.status_code >= 400
