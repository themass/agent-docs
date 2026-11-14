"""指标登记簿与 /metrics、/metrics/snapshot 两个端点。

指标现在由 agentkit 提供（与 job-come 共用词汇），所以测试断言的是它的名字：
``llm_calls_total`` / ``agent_phase_duration_seconds`` / ``agent_turns_total`` 等。

agentkit 没有"重置注册表"这种东西——计数器是进程级的，真实服务里也不会重开。
所以每个用例用**唯一的标签值**（模型名、角色名）把自己隔开，而不是清空全局状态。
这样测试之间不会互相污染，也不会测出一个线上不存在的行为。
"""

import uuid

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from companion import metrics
from companion.agent.brain.llm_trace import LlmCallCollector


def _tag(prefix: str) -> str:
    """每个用例一个唯一标签值。"""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _text() -> str:
    return metrics.render().decode()


async def test_a_model_call_moves_the_counters():
    model = _tag("m")
    collector = LlmCallCollector()
    reply = AIMessage(content="嗯", usage_metadata={"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
                      response_metadata={"model_name": model})
    await GenericFakeChatModel(messages=iter([reply])).ainvoke(
        [HumanMessage(content="在吗")], config={"callbacks": [collector]})

    text = _text()
    assert f'model="{model}"' in text
    assert 'llm_calls_total{' in text
    assert "llm_call_duration_seconds_count" in text
    # token 用量按方向分开：input 和 output 回答的是不同的问题
    assert "llm_tokens_total{" in text


async def test_metrics_are_written_without_anyone_calling_drain():
    """这条防的是这样的改动：把写指标挪到 drain 的调用方去——而那个调用方只在 QA 打开时存在。
    改了不会让任何测试失败，只会让线上的 /metrics 在关掉 QA 后变空。"""
    model = _tag("nodrain")
    reply = AIMessage(content="嗯", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                      response_metadata={"model_name": model})
    collector = LlmCallCollector()
    await GenericFakeChatModel(messages=iter([reply])).ainvoke(
        [HumanMessage(content="在吗")], config={"callbacks": [collector]})

    # 没有调用 drain()，指标已经在了
    assert f'model="{model}"' in _text()
    assert len(collector.drain()) == 1     # 记录仍然攒着，等着被追踪用


async def test_streaming_records_time_to_first_token():
    model = _tag("stream")
    collector = LlmCallCollector()
    chunks = [c async for c in GenericFakeChatModel(messages=iter([AIMessage(content="一二三")])).astream(
        [HumanMessage(content="数数")], config={"callbacks": [collector]})]
    assert chunks
    # 首 token 记成独立的 phase：首字慢和出字慢是两件事，不能合成一个数
    assert 'phase="llm_ttft"' in _text()


def test_a_failed_call_is_counted_under_its_error_name():
    model = _tag("fail")
    collector = LlmCallCollector()
    run_id = uuid.uuid4()
    collector.on_chat_model_start({}, [[HumanMessage(content="hi")]], run_id=run_id,
                                  metadata={"ls_model_name": model})
    collector.on_llm_error(TimeoutError("slow"), run_id=run_id)

    text = _text()
    assert f'model="{model}"' in text
    assert "llm_calls_total" in text
    assert 'status="error"' in text
    assert 'error_type="TimeoutError"' in text


def test_turn_state_and_duration_are_recorded():
    role = _tag("role")
    metrics.observe_turn(state="done", duration_sec=4.2, ttft_sec=1.1, role=role)
    text = _text()
    assert f'role="{role}"' in text
    assert 'status="done"' in text
    assert 'phase="turn"' in text
    assert 'phase="ttft"' in text


def test_phase_and_restart_are_recorded():
    phase = _tag("ph")
    metrics.observe_phase(phase=phase, duration_sec=0.25)
    assert f'phase="{phase}"' in _text()
    metrics.count_restart()
    assert "agent_turn_restarts_total" in _text()


def test_every_series_carries_application_and_env():
    """面板靠这两个标签区分"哪个服务、哪套环境"。缺了它们，多套部署的图会混在一起。"""
    metrics.observe_phase(phase=_tag("tagged"), duration_sec=0.1)
    for line in _text().splitlines():
        if line.startswith("agent_phase_duration_seconds_count{"):
            assert 'application="companion-agent"' in line
            assert 'env="' in line
            return
    raise AssertionError("没找到 agent_phase_duration_seconds")


def test_the_endpoint_serves_prometheus_text():
    """端点这一层：真的走一遍 FastAPI 路由，确认 content-type 和前缀。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from companion.api.http.routers.chat import build_health_router
    from companion.service.chat.lifecycle import DrainState

    phase = _tag("http")
    metrics.observe_phase(phase=phase, duration_sec=0.5)

    app = FastAPI()
    app.include_router(build_health_router(DrainState()))
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert f'phase="{phase}"' in response.text


def test_the_snapshot_endpoint_serves_json_with_the_same_numbers():
    """面板读 JSON，Prometheus 读文本，两者必须是同一份数据——否则图和对账对不上。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from companion.api.http.routers.chat import build_health_router
    from companion.service.chat.lifecycle import DrainState

    role = _tag("snap")
    metrics.observe_turn(state="done", duration_sec=2.0, ttft_sec=0.9, role=role)

    app = FastAPI()
    app.include_router(build_health_router(DrainState()))
    with TestClient(app) as client:
        payload = client.get("/metrics/snapshot").json()

    assert payload["service"] == "companion-agent"
    assert payload["enabled"] is True
    assert "pid" in payload and "host" in payload
    # 面板按 agentkit 的前缀过滤；我们自己的重跑计数器用 agent_ 前缀，所以也在里面
    assert "agent_turns" in payload["families"]
    turns = payload["families"]["agent_turns"]
    assert any(s["labels"].get("role") == role for s in turns["series"])
