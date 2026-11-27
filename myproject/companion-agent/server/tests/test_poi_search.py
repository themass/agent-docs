"""位置问答工具：无 key 降级与高德 POI 解析均使用离线 fake。"""

import json
from companion.agent.brain.deerflow import DeerFlowBrain
from companion.agent.brain.port import TurnRequest
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


async def test_fake_amap_json_is_parsed_and_current_location_wins():
    client = FakePoiHttpClient(payload={"status": "1", "pois": [{
        "name": "示例餐厅", "address": "示例路 1 号", "distance": "420", "type": "餐饮服务;中餐厅"
    }]})
    registry = _registry(amap_key="test-only-key", client=client)
    runtime = ToolRuntime(registry=registry, confirmations=NoopConfirmations())
    turn = ToolTurn(owner_id=7, session_id=1, turn_id="t2", character_id="role", locale="zh-CN",
                    product="chat", allowed=frozenset({"poi_search"}),
                    location={"lat": 31.23, "lng": 121.47})

    outcome = await runtime.invoke(turn, "poi_search", {
        "query": "中餐", "radius_m": 1200, "limit": 1,
    })

    assert outcome.status == "executed"
    assert "示例餐厅" in outcome.model_text
    assert "420" in outcome.model_text
    url, params = client.calls[0]
    assert url.endswith("/place/around")
    assert params["location"] == "121.47,31.23"
    assert params["radius"] == "1200"
    assert params["offset"] == "1"
    assert "test-only-key" not in outcome.model_text


def test_turn_context_carries_server_location_not_model_arguments():
    location = {"lat": 31.23, "lng": 121.47, "accuracy_m": 20.0}
    brain = DeerFlowBrain(None, tool_runtime=object(), tool_allowed=frozenset({"poi_search"}))
    context = brain._context(TurnRequest(
        user_id="7", character_id="role", message="附近有什么好吃的?", metadata={"location": location}
    ), "t3")
    assert context["tool_turn"].location == location


async def test_missing_or_invalid_turn_location_never_calls_provider_or_uses_model_coordinates():
    assert set(PoiSearchParams.model_fields) == {"query", "radius_m", "limit"}
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
