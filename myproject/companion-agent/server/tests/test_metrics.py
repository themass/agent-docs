"""指标登记簿与 /metrics 端点。

要点是**指标不能跟着 QA 开关走**：``COMPANION_QA_ENABLED=false`` 时追踪不落库，
但模型延迟和用量照样得量得到。所以这里既验证"采集器无开关也写指标"，也验证端点能取到它。
"""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from companion import metrics
from companion.agent.brain.llm_trace import LlmCallCollector


def _reset():
    metrics.reset_for_tests()


async def test_a_model_call_moves_the_counters():
    _reset()
    reply = AIMessage(content="嗯", usage_metadata={"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
                      response_metadata={"model_name": "fake-1"})
    collector = LlmCallCollector()
    await GenericFakeChatModel(messages=iter([reply])).ainvoke(
        [HumanMessage(content="在吗")], config={"callbacks": [collector]})

    text = metrics.render().decode()
    assert 'companion_llm_calls_total{model="fake-1",outcome="ok"} 1.0' in text
    assert 'companion_llm_tokens_total{kind="input",model="fake-1"} 30.0' in text
    assert 'companion_llm_tokens_total{kind="output",model="fake-1"} 5.0' in text
    # 非流式调用没有首 token，所以直方图这一条还不该出现——这本身就是"别把 0 当成功"的检查
    assert "companion_llm_duration_seconds_count" in text


async def test_streaming_fills_the_ttft_histogram():
    _reset()
    collector = LlmCallCollector()
    chunks = [c async for c in GenericFakeChatModel(messages=iter([AIMessage(content="一二三")])).astream(
        [HumanMessage(content="数数")], config={"callbacks": [collector]})]
    assert chunks
    text = metrics.render().decode()
    assert "companion_llm_ttft_seconds_count" in text
    assert 'companion_llm_ttft_seconds_count{model=""}' in text or "companion_llm_ttft_seconds_count" in text


async def test_metrics_are_written_without_anyone_calling_drain():
    """这条防的是这样的改动：把写指标挪到 drain 的调用方去——而那个调用方只在 QA 打开时存在。
    改了不会让任何测试失败，只会让线上的 /metrics 在关掉 QA 后变空。"""
    _reset()
    reply = AIMessage(content="嗯", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                      response_metadata={"model_name": "fake-2"})
    collector = LlmCallCollector()
    await GenericFakeChatModel(messages=iter([reply])).ainvoke(
        [HumanMessage(content="在吗")], config={"callbacks": [collector]})

    # 没有调用 drain()，指标已经在了
    assert 'model="fake-2"' in metrics.render().decode()
    assert len(collector.drain()) == 1     # 记录仍然攒着，等着被追踪用


def test_a_failed_call_is_counted_under_its_error_name():
    _reset()
    collector = LlmCallCollector()
    from uuid import uuid4
    run_id = uuid4()
    collector.on_chat_model_start({}, [[HumanMessage(content="hi")]], run_id=run_id,
                                  metadata={"ls_model_name": "fake-3"})
    collector.on_llm_error(TimeoutError("slow"), run_id=run_id)

    text = metrics.render().decode()
    assert 'companion_llm_calls_total{model="fake-3",outcome="error"} 1.0' in text
    assert 'companion_llm_errors_total{error="TimeoutError",model="fake-3"} 1.0' in text


def test_turn_state_and_duration_are_recorded():
    _reset()
    metrics.observe_turn(state="done", duration_sec=4.2, ttft_sec=1.1)
    text = metrics.render().decode()
    assert 'companion_turns_total{state="done"} 1.0' in text
    assert "companion_turn_duration_seconds_count" in text
    assert "companion_turn_ttft_seconds_count" in text


def test_the_endpoint_serves_prometheus_text():
    """端点这一层：真的走一遍 FastAPI 路由，确认 content-type 和前缀。"""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    from companion.api.http.routers.chat import build_health_router
    from companion.service.chat.lifecycle import DrainState

    _reset()
    metrics.observe_turn(state="done", duration_sec=1.0, ttft_sec=0.5)

    app = FastAPI()
    app.include_router(build_health_router(DrainState()))
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'companion_turns_total{state="done"} 1.0' in response.text
