"""位置问答工具：无 key 降级与高德 POI 解析均使用离线 fake。"""

import json
from companion.agent.brain.deerflow import DeerFlowBrain
from companion.agent.brain.port import TurnRequest
from companion.agent.prompt.templates import PLATFORM_LAYER, PROMPT_VERSION
from companion.agent.tools.registry import ToolRegistry
from companion.agent.tools.runtime import ToolRuntime, ToolTurn
from companion.service.tools_impl.builtin import PoiSearchParams, register_builtin_tools
from companion.service.tools_impl.poi_search import AmapPoiSearch, PoiSearchConfig


class NoopConfirmations:
    async def create(self, _record):
        raise AssertionError("read-only tool must not request confirmation")


class FakePoiHttpClient:
    def __init__(self, status=200, payload=None, body=None):
        self.status = status
        self.payload = payload or {"status": "1", "pois": []}
        self.body = body
        self.calls = []

    async def get(self, url, *, params):
        self.calls.append((url, dict(params)))
        body = self.body if self.body is not None else json.dumps(self.payload).encode()
        return self.status, body


def _registry(*, amap_key="", client=None):
    registry = ToolRegistry()
    register_builtin_tools(registry, memory=object(), timeline=object(),
                           amap_key=amap_key, poi_http_client=client)
    return registry


async def test_missing_key_returns_not_configured_in_model_context():
    registry = _registry()
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="t1", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}),
                    location={"lat": 31.23, "lng": 121.47})

    outcome = await runtime.invoke(turn, "poi_search", {"query": "好吃的"})

    assert outcome.status == "executed"
    model_envelope = json.loads(outcome.model_text)
    result = json.loads(model_envelope["result"])
    assert result["status"] == "not_configured"
    assert result["message"] == "未接入地图服务"


async def test_destination_search_returns_only_provider_distance_from_current_location():
    client = FakePoiHttpClient(payload={"status": "1", "pois": [{
        "name": "示例医院", "address": "示例路 1 号", "distance": "420", "type": "医疗保健服务;医院"
    }]})
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="t2", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}),
                    location={"lat": 31.23, "lng": 121.47})

    outcome = await runtime.invoke(turn, "poi_search", {
        "query": "市立医院", "radius_m": 1200, "limit": 1,
    })

    assert outcome.status == "executed"
    assert "示例医院" in outcome.model_text
    assert "420" in outcome.model_text
    url, params = client.calls[0]
    assert url.endswith("/place/around")
    assert params["location"] == "121.47,31.23"
    assert params["radius"] == "1200"
    assert params["offset"] == "1"
    assert params["keywords"] == "市立医院"
    assert "test-only-key" not in outcome.model_text


async def test_region_without_current_location_uses_scoped_text_search_without_distance():
    client = FakePoiHttpClient(payload={"status": "1", "pois": [{
        "name": "示例咖啡店", "address": "示例路 2 号", "type": "餐饮服务;咖啡厅"
    }]})
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="region", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}))

    outcome = await runtime.invoke(turn, "poi_search", {
        "query": "咖啡", "region": "上海市", "lat": 0, "lng": 0,
    })

    assert outcome.status == "executed"
    result = json.loads(json.loads(outcome.model_text)["result"])
    assert result["status"] == "ok"
    assert result["pois"][0]["distance_m"] is None
    url, params = client.calls[0]
    assert url.endswith("/place/text")
    assert params["city"] == "上海市"
    assert "location" not in params
    assert "radius" not in params
    assert "sortrule" not in params


async def test_empty_region_search_returns_no_pois():
    client = FakePoiHttpClient(payload={"status": "1", "pois": []})
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="empty", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}))

    outcome = await runtime.invoke(turn, "poi_search", {
        "query": "游泳池", "region": "上海市",
    })

    result = json.loads(json.loads(outcome.model_text)["result"])
    assert result == {"status": "ok", "pois": []}


def test_platform_guidance_is_intent_led_and_sets_distance_limits():
    assert PROMPT_VERSION == "2026-11-26.4"
    assert "不要每轮固定调用" in PLATFORM_LAYER
    assert "医院、泳池、健身房、景点" in PLATFORM_LAYER
    assert "地图返回的邻近距离" in PLATFORM_LAYER
    assert "路线距离或预计时间" in PLATFORM_LAYER
    assert "status=invalid_location" in PLATFORM_LAYER
    assert "status=query_failed" in PLATFORM_LAYER
    assert "结果为空" in PLATFORM_LAYER


def test_turn_context_carries_server_location_not_model_arguments():
    location = {"lat": 31.23, "lng": 121.47, "accuracy_m": 20.0}
    brain = DeerFlowBrain(None, tool_runtime=object(), tool_allowed=frozenset({"poi_search"}))
    context = brain._context(TurnRequest(
        user_id="7", character_id="role", message="附近有什么好吃的?", metadata={"location": location}
    ), "t3")
    assert context["tool_turn"].location == location


async def test_missing_or_invalid_turn_location_never_calls_provider_or_uses_model_coordinates():
    assert set(PoiSearchParams.model_fields) == {"query", "radius_m", "limit", "region"}
    client = FakePoiHttpClient()
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    invalid_locations = [
        None,
        {"lat": 31.23},
        {"lat": float("nan"), "lng": 121.47},
        {"lat": 91, "lng": 121.47},
        {"lat": True, "lng": 121.47},
    ]

    for index, location in enumerate(invalid_locations):
        turn = ToolTurn(owner_id=7, session_id=1, turn_id=f"t{index}", character_id="role",
                        locale="zh-CN", product="chat", allowed=frozenset({"poi_search"}),
                        location=location)
        outcome = await runtime.invoke(turn, "poi_search", {
            "query": "附近美食", "lat": 0, "lng": 0,
        })

        assert outcome.status == "executed"
        result = json.loads(json.loads(outcome.model_text)["result"])
        assert result["status"] == "invalid_location"
        assert result["pois"] == []

    assert client.calls == []


async def test_upstream_error_body_is_not_returned_to_model_or_logged(caplog):
    client = FakePoiHttpClient(status=503, body=b"provider-secret-error-body")
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="t6", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}),
                    location={"lat": 31.23, "lng": 121.47})

    outcome = await runtime.invoke(turn, "poi_search", {"query": "咖啡"})

    assert "provider-secret-error-body" not in outcome.model_text
    assert "test-only-key" not in outcome.model_text
    assert "provider-secret-error-body" not in caplog.text
    assert "test-only-key" not in caplog.text


async def test_failed_amap_call_returns_structured_query_failed():
    client = FakePoiHttpClient(status=503)
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="t4", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}),
                    location={"lat": 31.23, "lng": 121.47})

    outcome = await runtime.invoke(turn, "poi_search", {"query": "咖啡"})

    assert outcome.status == "executed"
    result = json.loads(json.loads(outcome.model_text)["result"])
    assert result["status"] == "query_failed"
    assert result["message"] == "地图查询失败"
