"""对外路径只有一个：``/v1``。

产品未上线，没有已安装的客户端需要兼容，所以不做旧前缀别名——
两套前缀只会让人以为有两套实现，而那正是重构前「同一功能两个入口、两套数据」的成因。
这条测试守住「旧路径确实不再存在」，避免有人悄悄把它加回来。
"""

import os

import pytest
from fastapi.testclient import TestClient

URL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")

ME = {"Authorization": "Bearer 12345"}


@pytest.fixture(scope="module")
def client():
    from companion.brain.fake import FakeBrain
    from companion.memory.fake import InMemoryMemoryPort
    from companion.bootstrap.app import create_app
    from companion.bootstrap.platform import default_prompts
    from companion.bootstrap.platform import build_platform
    from companion.config import Settings

    settings = Settings(companion_mysql_url=URL, companion_redis_url=os.environ.get("COMPANION_TEST_REDIS_URL", ""))
    platform = build_platform(settings, brain=FakeBrain(["好"]), prompts=default_prompts(),
                              memory_port=InMemoryMemoryPort())
    app = create_app(livekit_url="", platform=platform)
    with TestClient(app) as c:
        yield c


def test_v1_is_the_public_prefix(client):
    assert client.get("/v1/roles?limit=2&lang=zh", headers=ME).status_code == 200


def test_the_old_prefix_is_gone(client):
    assert client.get("/api/agent/v1/roles?limit=2", headers=ME).status_code == 404


def test_query_string_survives(client):
    items = client.get("/v1/roles?limit=2&lang=zh", headers=ME).json().get("items") or []
    assert len(items) <= 2


def test_writes_land_in_the_same_storage(client):
    created = client.post("/v1/sessions", json={"role_id": "linche", "name": "路径测试"}, headers=ME)
    assert created.status_code == 201, created.text
    sid = created.json()["id"]
    assert client.get(f"/v1/sessions/{sid}/messages", headers=ME).status_code == 200
