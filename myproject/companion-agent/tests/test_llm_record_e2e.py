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

from companion.adapters.brain.deerflow import DeerFlowBrain
from companion.ports.brain import TextDelta, TurnRequest

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
        callbacks = [request.metadata["llm_collector"]]
        async for chunk in self._model.astream([HumanMessage(content=request.message)],
                                               config={"callbacks": callbacks}):
            yield TextDelta(str(chunk.content))

    async def aclose(self):
        return None


pytestmark_e2e = pytest.mark.skipif(not (DB and REDIS), reason="needs COMPANION_TEST_DATABASE_URL and _REDIS_URL")


def _platform(brain):
    from companion.bootstrap.platform import build_platform, default_prompts
    from companion.config import Settings

    return build_platform(Settings(_env_file=None, companion_database_url=DB, companion_redis_url=REDIS),
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


async def _calls(platform, user):
    from companion.adapters.store.sql.schema import llm_call

    async with platform.engine.connect() as conn:
        return (await conn.execute(select(llm_call).where(llm_call.c.owner_id == user))).mappings().all()


@pytestmark_e2e
async def test_a_turn_records_metrics_but_not_content_without_consent():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    reply = AIMessage(content="先歇一会儿", usage_metadata={"input_tokens": 50, "output_tokens": 6, "total_tokens": 56},
                      response_metadata={"finish_reason": "stop"})
    platform = _platform(_ModelBrain(reply))
    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        _turn(client, user)
    rows = await _calls(platform, user)
    assert len(rows) == 1 and not rows[0]["content_kept"]
    assert rows[0]["output_text"] is None and rows[0]["input_messages"] is None
    assert (rows[0]["input_tokens"], rows[0]["output_tokens"], rows[0]["finish_reason"]) == (50, 6, "stop")
    assert rows[0]["prompt_version"] and rows[0]["role_id"] == "linche" and rows[0]["turn_id"]


@pytestmark_e2e
async def test_with_consent_the_turn_content_is_recorded():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    platform = _platform(_ModelBrain(AIMessage(content="先歇一会儿")))
    with TestClient(create_app(livekit_url="", platform=platform)) as client:
        h = {"Authorization": f"Bearer {user}"}
        assert client.patch("/v1/consent", json={"qa_retention": True}, headers=h).json()["qa_retention"] is True
        _turn(client, user, text="今天好累")
    (row,) = await _calls(platform, user)
    assert row["content_kept"] and row["output_text"] == "先歇一会儿"
    assert row["input_messages"][-1]["content"] == "今天好累"


@pytestmark_e2e
async def test_consent_defaults_to_off():
    from companion.bootstrap.app import create_app

    user = random.randint(10**6, 10**7)
    with TestClient(create_app(livekit_url="", platform=_platform(_ModelBrain(AIMessage(content="x"))))) as client:
        assert client.get("/v1/consent", headers={"Authorization": f"Bearer {user}"}).json()["qa_retention"] is False


async def _turns(platform, user):
    from companion.adapters.store.sql.schema import chat_turn

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
    (call,) = await _calls(platform, user)
    assert call["turn_id"] == turn["id"]                # 汇总行与明细行能对上
