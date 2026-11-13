"""回合接口与管线的集成测试。

不需要 fastapi 也能跑的部分（管线、取消）走纯逻辑；HTTP 层在装了 fastapi 的
环境里额外覆盖，没装就跳过——这个包的核心不该被 web 栈绑死。
"""

import asyncio

import pytest

from companion.brain.fake import FakeBrain
from companion.brain.port import BrainTurn, TurnRequest
from companion.turn.pipeline import TurnPipeline


async def drain(pipeline, request):
    return [out async for out in pipeline.run(request)]


def req(message="在吗"):
    return TurnRequest(user_id="u1", character_id="linche", message=message)


async def test_pipeline_emits_one_sentence_at_a_time():
    brain = FakeBrain(["我最近。", "有点卡住。"])
    out = await drain(TurnPipeline(brain), req())
    assert [o.text for o in out] == ["我最近。", "有点卡住。"]


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
