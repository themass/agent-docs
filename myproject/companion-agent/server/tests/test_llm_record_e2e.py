"""模型调用记录端到端：回合 → 采集 → 同意判断 → 落库。

前半（大脑把回调传给图）不依赖外部服务；整条链路需要 Redis（COMPANION_TEST_REDIS_URL）和一个库
（COMPANION_TEST_DATABASE_URL，SQLite 即可），否则跳过。
"""

import os
import random

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select

from companion.agent.brain.deerflow import DeerFlowBrain
from companion.agent.brain.port import TextDelta, TurnRequest

DB = os.environ.get("COMPANION_TEST_DATABASE_URL", "")
REDIS = os.environ.get("COMPANION_TEST_REDIS_URL", "")


class _Graph:
    def __init__(self):
        self.kwargs = None

    async def astream(self, payload, **kwargs):
        self.kwargs = kwargs
        yield AIMessage(content="好"), {}


async def test_the_collector_is_handed_to_the_graph_even_without_a_checkpoint():
    graph, marker = _Graph(), object()
    brain = DeerFlowBrain(graph, stateful=False)     # 无状态：_config() 为 None，回调仍必须传进去
    request = TurnRequest(user_id="1", character_id="linche", message="hi", metadata={"llm_collector": marker})
    events = [e async for e in brain.run(request)]
    assert any(isinstance(e, TextDelta) for e in events)
    assert graph.kwargs["config"]["callbacks"] == [marker]


async def test_no_collector_means_no_callbacks_key():
    graph = _Graph()
    request = TurnRequest(user_id="1", character_id="linche", message="hi")
    [e async for e in DeerFlowBrain(graph).run(request)]
    assert "config" not in graph.kwargs


class _ModelBrain:
    """带 run 的假大脑：真的调一个 LangChain 模型，并把请求里的采集器当回调传下去，和 DeerFlowBrain 做的一样。"""

    def __init__(self, reply):
        from test_llm_trace import StreamingModel

        text = reply.content
        self._model = StreamingModel(pieces=[text[: len(text) // 2], text[len(text) // 2:]],
                                     usage=reply.usage_metadata or {"input_tokens": 1, "output_tokens": 1,
                                                                    "total_tokens": 2})

    async def run(self, request, inbox=None):
        collector = request.metadata.get("llm_collector")       # 总开关关着时没有采集器，真实的大脑也是这样处理
        callbacks = [collector] if collector is not None else []
        async for chunk in self._model.astream([HumanMessage(content=request.message)],
                                               config={"callbacks": callbacks}):
            yield TextDelta(str(chunk.content))

    async def aclose(self):
        return None


pytestmark_e2e = pytest.mark.skipif(not (DB and REDIS), reason="needs COMPANION_TEST_DATABASE_URL and _REDIS_URL")


def _platform(brain, **settings):
    from companion.bootstrap.platform import build_platform, default_prompts
    from companion.config import Settings

    return build_platform(Settings(_env_file=None, companion_database_url=DB, companion_redis_url=REDIS, **settings),
                          brain=brain, prompts=default_prompts())


def _turn(client, user: int, text="今天好累"):
    h = {"Authorization": f"Bearer {user}"}
    sid = client.post("/v1/sessions", json={"role_id": "linche"}, headers=h).json()["id"]
    assert client.post(f"/v1/sessions/{sid}/messages", json={"text": text}, headers=h).status_code == 202
    import time
    for _ in range(100):
        msgs = client.get(f"/v1/sessions/{sid}/messages", headers=h).json()
        items = msgs.get("items", msgs) if isinstance(msgs, dict) else msgs
        if any(m["role"] == "assistant" for m in items):
            return sid
        time.sleep(0.05)
    raise AssertionError("assistant never replied")


async def _traces(platform, user):
    from companion.db.schema import turn_trace

    async with platform.engine.connect() as conn:
        return (await conn.execute(select(turn_trace).where(turn_trace.c.owner_id == user))).mappings().all()


async def _blob_count(platform, user):
    """只数这个用户的文本块。整张表的数会带上别的测试、上一次运行留下的块。"""
    from sqlalchemy import func

    from companion.db.schema import text_blob

    async with platform.engine.connect() as conn:
        return (await conn.execute(select(func.count()).select_from(text_blob)
                                   .where(text_blob.c.owner_id == user))).scalar_one()


async def _read(platform, user):
    (row,) = await _traces(platform, user)
    return await platform.qa.read_trace(turn_id=row["turn_id"], owner_id=user)


@pytestmark_e2e
async def test_a_turn_records_metrics_but_not_content_without_consent():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    reply = AIMessage(content="先歇一会儿", usage_metadata={"input_tokens": 50, "output_tokens": 6, "total_tokens": 56},
                      response_metadata={"finish_reason": "stop"})
    platform = _platform(_ModelBrain(reply))
    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        _turn(client, user)
    t = await _read(platform, user)
    assert t["content_kept"] is False and len(t["steps"]) == 1
    step = t["steps"][0]
    assert step["input"] == []                                  # 没有正文：还原出来的输入是空的
    assert "output" not in step and "reasoning" not in step
    assert (step["in"], step["out"], step["fr"]) == (50, 6, "stop")
    assert t["role_id"] == "linche"
    assert await _blob_count(platform, user) == 0


@pytestmark_e2e
async def test_with_consent_the_whole_turn_can_be_reconstructed():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    platform = _platform(_ModelBrain(AIMessage(content="先歇一会儿")))
    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        h = {"Authorization": f"Bearer {user}"}
        assert client.patch("/v1/consent", json={"qa_retention": True}, headers=h).json()["qa_retention"] is True
        _turn(client, user, text="今天好累")
    t = await _read(platform, user)
    assert t["content_kept"] is True
    (step,) = t["steps"]
    assert step["output"] == "先歇一会儿"
    assert step["input"][-1] == {"role": "human", "content": "今天好累"}


@pytestmark_e2e
async def test_consent_defaults_to_off():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    with TestClient(create_app(livekit_url="", platform=_platform(_ModelBrain(AIMessage(content="x"))))) as client:
        assert client.get("/v1/consent", headers={"Authorization": f"Bearer {user}"}).json()["qa_retention"] is False


async def _turns(platform, user):
    from companion.db.schema import chat_turn

    async with platform.engine.connect() as conn:
        return (await conn.execute(select(chat_turn).where(chat_turn.c.owner_id == user))).mappings().all()


@pytestmark_e2e
async def test_the_turn_summary_records_model_skills_usage_and_final_state():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    platform = _platform(_ModelBrain(AIMessage(content="先歇一会儿",
                                               usage_metadata={"input_tokens": 50, "output_tokens": 6, "total_tokens": 56})))
    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        _turn(client, user)
        import time
        time.sleep(0.3)      # after_turn 在回复交付之后才跑
    (turn,) = await _turns(platform, user)
    assert turn["state"] == "done" and turn["finished_at"] is not None and turn["started_at"] is not None
    assert turn["role_id"] == "linche" and turn["prompt_version"]
    assert "companion-core" in turn["skills"]           # 常驻的陪伴底线也算“这一轮用了的 skill”
    assert turn["usage"]["calls"] == 1 and turn["usage"]["output_tokens"] == 6
    (trace,) = await _traces(platform, user)
    assert trace["turn_id"] == turn["id"]                # 汇总行与追踪行能对上


@pytestmark_e2e
async def test_a_slow_trace_store_does_not_delay_the_reply():
    """记录是旁路。追踪库慢（远程库往返几百毫秒很常见）不能让用户多等，更不能让会话锁多占。"""
    import time

    from companion.bootstrap.app import create_app

    DELAY = 1.5
    user = random.randint(10**6, 10**7)
    platform = _platform(_ModelBrain(AIMessage(content="先歇一会儿")))
    qa = platform.qa
    for name in ("record_trace", "note_turn_models", "finish_turn"):
        original = getattr(qa, name, None)
        if original is None:
            continue

        def slow(original=original):
            async def wrapped(*a, **kw):
                await __import__("asyncio").sleep(DELAY)
                return await original(*a, **kw)
            return wrapped
        setattr(qa, name, slow())

    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        t0 = time.monotonic()
        _turn(client, user)
        waited = time.monotonic() - t0
    assert waited < DELAY * 0.6, f"reply took {waited:.2f}s: the trace write is on the reply path"


@pytestmark_e2e
async def test_with_the_switch_off_nothing_is_recorded_but_the_chat_still_works():
    from companion.db.schema import chat_turn
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    platform = _platform(_ModelBrain(AIMessage(content="先歇一会儿")), companion_qa_enabled=False)
    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        h = {"Authorization": f"Bearer {user}"}
        client.patch("/v1/consent", json={"qa_retention": True}, headers=h)       # 用户同意了，开关关着也不能存
        sid = _turn(client, user)
        msgs = client.get(f"/v1/sessions/{sid}/messages", headers=h).json()
        items = msgs.get("items", msgs) if isinstance(msgs, dict) else msgs
        assert any(m["role"] == "assistant" for m in items)                        # 对话本身不受影响（列表是最新在前，不看顺序）
    assert await _traces(platform, user) == []
    async with platform.engine.connect() as conn:
        assert (await conn.execute(select(chat_turn).where(chat_turn.c.owner_id == user))).all() == []
    assert await _blob_count(platform, user) == 0
    assert platform.qa_enabled is False


@pytestmark_e2e
async def test_the_switch_is_on_by_default():
    platform = _platform(_ModelBrain(AIMessage(content="x")))
    assert platform.qa_enabled is True
