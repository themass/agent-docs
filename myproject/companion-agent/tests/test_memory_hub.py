"""memory_hub 的作用域隔离、启动校验，以及记忆接口的归属（D §10）。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.adapters.timeline.memory import InMemoryTimeline
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.memory_v1 import build_router
from memory_hub import AppConfig, MemoryHub, UnknownApp, compose_user_id, validate_configs
from memory_hub.config import ConfigError
from memory_hub.scope import ScopeError, split_user_id


class Port:
    def __init__(self):
        self.rows = {}

    async def add(self, uid, items):
        self.rows.setdefault(uid, []).extend(items)
        return list(items)

    async def search(self, uid, query, limit=5, kinds=None):
        pool = self.rows.get(uid, [])
        if kinds:
            pool = [r for r in pool if r.kind in {str(getattr(k, "value", k)) for k in kinds}]
        return pool[:limit]

    async def list_for_user(self, uid, limit=20, offset=0, include_history=False):
        rows = self.rows.get(uid, [])
        if not include_history:
            rows = [r for r in rows if getattr(r, "is_latest", True)]
        return rows[offset:offset + limit]

    async def supersede(self, uid, old_id, item):
        rows = self.rows.get(uid, [])
        if not any(r.id == old_id for r in rows):
            return None
        # 与真实后端一致：旧条目标为被取代、保留在历史里；新条目追加
        from dataclasses import replace
        self.rows[uid] = [replace(r, is_latest=False) if r.id == old_id else r for r in rows] + [item]
        return item

    async def delete_one(self, uid, memory_id):
        rows = self.rows.get(uid, [])
        keep = [r for r in rows if r.id != memory_id]
        self.rows[uid] = keep
        return len(keep) != len(rows)

    async def delete_user(self, uid):
        return len(self.rows.pop(uid, []))


CONFIGS = [AppConfig("companion"), AppConfig("jobcome")]


def test_composite_ids_and_their_validation():
    assert compose_user_id("companion", "42") == "companion:42"
    assert split_user_id("jobcome:7") == ("jobcome", "7")
    with pytest.raises(ScopeError):
        compose_user_id("companion", "a:b")
    with pytest.raises(ScopeError):
        compose_user_id("Bad!", "1")


def test_startup_refuses_duplicate_or_unknown_apps():
    with pytest.raises(ConfigError):
        validate_configs([AppConfig("companion"), AppConfig("companion")])
    with pytest.raises(ConfigError):
        validate_configs([AppConfig("companion", backend="qdrant")])
    with pytest.raises(ConfigError):
        validate_configs([AppConfig("Bad!")])
    validate_configs(CONFIGS)


async def test_two_apps_sharing_one_backend_still_cannot_see_each_other():
    port = Port()
    hub = MemoryHub.from_config(CONFIGS, lambda cfg: port)
    companion, jobcome = hub.for_app("companion"), hub.for_app("jobcome")
    await companion.add("7", [SimpleNamespace(id="a", content="喜欢茶")])
    await jobcome.add("7", [SimpleNamespace(id="b", content="求职 Python")])
    assert [r.content for r in await companion.search("7", "x")] == ["喜欢茶"]
    assert [r.content for r in await jobcome.search("7", "x")] == ["求职 Python"]
    assert await jobcome.delete_one("7", "a") is False
    assert len(await companion.list_for_user("7")) == 1


async def test_kinds_are_passed_through_to_the_backend():
    """kinds 原样透传给后端，由后端过滤（规范 §3），而不是在 hub 里事后过滤。"""
    port = Port()
    hub = MemoryHub.from_config(CONFIGS, lambda cfg: port)
    companion = hub.for_app("companion")
    fact = SimpleNamespace(id="f", content="喜欢茶", kind="FACT")
    event = SimpleNamespace(id="e", content="面试", kind="EVENT")
    await companion.add("7", [fact, event])
    assert [r.id for r in await companion.search("7", "x", kinds=["EVENT"])] == ["e"]


def test_unknown_app_is_refused():
    hub = MemoryHub.from_config(CONFIGS, lambda cfg: Port())
    with pytest.raises(UnknownApp):
        hub.for_app("nope")


@pytest.fixture
def memory_client():
    hub = MemoryHub.from_config(CONFIGS, lambda cfg: Port())
    app = FastAPI()
    app.include_router(build_router(memory=hub.for_app("companion"), timeline=InMemoryTimeline(),
                                    current_user=build_current_user(AllowAllVerifier())))
    return TestClient(app)


ME = {"Authorization": "Bearer 7"}
BOB = {"Authorization": "Bearer 8"}


def test_fact_endpoints_respect_ownership(memory_client):
    fid = memory_client.post("/api/agent/v1/memory/facts", json={"content": "喜欢喝茶"}, headers=ME).json()["id"]
    assert memory_client.get("/api/agent/v1/memory/facts", headers=BOB).json()["items"] == []
    assert memory_client.delete(f"/api/agent/v1/memory/facts/{fid}", headers=BOB).status_code == 404
    # 改写 = 取代：旧条目保留在历史里，新条目接上它
    edited = memory_client.patch(f"/api/agent/v1/memory/facts/{fid}", json={"content": "更喜欢绿茶"},
                                 headers=ME)
    assert edited.status_code == 200 and edited.json()["content"] == "更喜欢绿茶"
    current = memory_client.get("/api/agent/v1/memory/facts", headers=ME).json()["items"]
    assert [i["content"] for i in current] == ["更喜欢绿茶"]
    history = memory_client.get("/api/agent/v1/memory/facts?include_history=true", headers=ME).json()["items"]
    assert len(history) == 2


def test_event_endpoints_respect_ownership_and_update_status(memory_client):
    eid = memory_client.post("/api/agent/v1/memory/events",
                             json={"title": "评审", "at": "2026-12-01T10:00:00+00:00"}, headers=ME).json()["id"]
    assert memory_client.delete(f"/api/agent/v1/memory/events/{eid}", headers=BOB).status_code == 404
    # 改了状态：完成的事件不再出现在「将来」列表里
    assert memory_client.patch(f"/api/agent/v1/memory/events/{eid}", json={"status": "done"},
                               headers=BOB).status_code == 404
    assert memory_client.patch(f"/api/agent/v1/memory/events/{eid}", json={"status": "done"},
                               headers=ME).status_code == 200
    assert memory_client.get("/api/agent/v1/memory/events", headers=ME).json()["items"] == []
    assert memory_client.patch(f"/api/agent/v1/memory/events/{eid}", json={"status": "nope"},
                               headers=ME).status_code == 422
    assert memory_client.delete(f"/api/agent/v1/memory/events/{eid}", headers=ME).status_code == 204


def test_profile_is_explicitly_empty_without_a_store(memory_client):
    """没有画像存储（未配置）或没有指定角色：明确返回空，不编造。"""
    empty = {"items": [], "markdown": None, "version": None}
    assert memory_client.get("/api/agent/v1/memory/profile", headers=ME).json() == empty
    assert memory_client.get("/api/agent/v1/memory/profile?role_id=linche", headers=ME).json() == empty
    assert memory_client.post("/api/agent/v1/memory/profile/1/suppress", headers=ME).status_code == 404
    assert memory_client.delete("/api/agent/v1/memory/profile/1", headers=ME).status_code == 404
