"""对外前缀：``/v1`` 与 ``/api/agent/v1`` 必须是同一份实现。

这条测试守的是架构约束本身：如果哪天有人把 ``/v1`` 接成另一套路由，
两条路径的响应就会出现差异——那正是重构前「同一功能两个入口、两套数据」的根因。
"""

import os

import pytest
from fastapi.testclient import TestClient

URL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")

ME = {"Authorization": "Bearer 12345"}


@pytest.fixture(scope="module")
def client():
    """必须带平台：``/api/agent/v1`` 的路由只在 platform 存在时才挂上。"""
    from companion.adapters.brain.fake import FakeBrain
    from companion.adapters.memory.fake import InMemoryMemoryPort
    from companion.bootstrap.app import create_app
    from companion.bootstrap.container import create_container
    from companion.bootstrap.platform import build_platform
    from companion.config import Settings

    container = create_container()
    settings = Settings(companion_mysql_url=URL, companion_redis_url=os.environ.get("COMPANION_TEST_REDIS_URL", ""))
    platform = build_platform(settings, brain=FakeBrain(["好"]), prompts=container.prompts,
                              memory_port=InMemoryMemoryPort())
    app = create_app(livekit_url="", run_initiative=False, platform=platform)
    with TestClient(app) as c:
        yield c


def test_both_prefixes_return_the_same_body(client):
    legacy = client.get("/api/agent/v1/roles?limit=2&lang=zh", headers=ME)
    canonical = client.get("/v1/roles?limit=2&lang=zh", headers=ME)
    assert canonical.status_code == legacy.status_code == 200
    assert canonical.json() == legacy.json()


def test_the_alias_does_not_leak_into_other_paths(client):
    # 只有 /v1 前缀被改写；别的前缀原样透传，仍然 404
    assert client.get("/v2/roles", headers=ME).status_code == 404
    assert client.get("/roles", headers=ME).status_code == 404


def test_v1_keeps_the_query_string(client):
    r = client.get("/v1/roles?limit=2&lang=zh", headers=ME)
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert len(items) <= 2, "查询参数丢失会退化成默认分页"


def test_write_endpoints_are_reachable_through_the_alias(client):
    created = client.post("/v1/sessions", json={"role_id": "linche", "name": "别名测试"}, headers=ME)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    # 同一个会话用旧前缀读得到，说明写入的是同一份存储
    legacy_view = client.get(f"/api/agent/v1/sessions/{sid}/messages", headers=ME)
    assert legacy_view.status_code == 200
