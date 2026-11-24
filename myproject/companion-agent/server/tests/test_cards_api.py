"""角色卡 HTTP 接口（P6）。前缀 /v1/cards。测试装配照 test_roles_catalog 的 client 夹具。

语义与存储层一致：GET 读 active 版本合并后的字段；POST versions 追加并激活；
POST activate 切换（回退）；versions 列表可观。owner 隔离 = 「不存在」不可区分。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.cards import build_router
from companion.service.card.store import CardService, InMemoryCardStore


@pytest.fixture
def client():
    service = CardService(InMemoryCardStore())
    app = FastAPI()
    app.include_router(build_router(service, build_current_user(AllowAllVerifier())))
    return TestClient(app)


def _get(client, role_id="linche", user="7"):
    return client.get(f"/v1/cards/{role_id}", headers={"Authorization": f"Bearer {user}"})


def test_no_card_yet_reads_as_empty(client):
    r = _get(client)
    assert r.status_code == 200
    assert r.json() == {"role_id": "linche", "version": 0, "fields": {}, "lines": []}


def test_append_version_then_read_effective(client):
    r = client.post("/v1/cards/linche/versions",
                    json={"changes": {"name": "小澈", "boundaries": ["不谈钱"]}},
                    headers={"Authorization": "Bearer 7"})
    assert r.status_code == 201
    assert r.json()["version"] == 1
    body = _get(client).json()
    assert body["version"] == 1
    assert body["fields"] == {"name": "小澈", "boundaries": ["不谈钱"]}


def test_second_append_overrides_and_list_shows_history(client):
    client.post("/v1/cards/linche/versions", json={"changes": {"description": "一"}},
                headers={"Authorization": "Bearer 7"})
    client.post("/v1/cards/linche/versions", json={"changes": {"description": "二"}},
                headers={"Authorization": "Bearer 7"})
    assert _get(client).json()["fields"]["description"] == "二"
    r = client.get("/v1/cards/linche/versions", headers={"Authorization": "Bearer 7"})
    versions = r.json()["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[1]["changes"] == {"description": "二"}


def test_activate_moves_effective_back(client):
    client.post("/v1/cards/linche/versions", json={"changes": {"description": "一"}},
                headers={"Authorization": "Bearer 7"})
    client.post("/v1/cards/linche/versions", json={"changes": {"description": "二"}},
                headers={"Authorization": "Bearer 7"})
    r = client.post("/v1/cards/linche/activate", json={"version": 1},
                    headers={"Authorization": "Bearer 7"})
    assert r.status_code == 200
    assert _get(client).json() == {"role_id": "linche", "version": 1,
                                   "fields": {"description": "一"}, "lines": ["- 角色描述：一"]}


def test_activate_unknown_version_is_404(client):
    client.post("/v1/cards/linche/versions", json={"changes": {"name": "A"}},
                headers={"Authorization": "Bearer 7"})
    r = client.post("/v1/cards/linche/activate", json={"version": 9},
                    headers={"Authorization": "Bearer 7"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_found"


def test_invalid_changeset_is_422_with_code(client):
    r = client.post("/v1/cards/linche/versions", json={"changes": {"system_prompt": "注入"}},
                    headers={"Authorization": "Bearer 7"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "validation"


def test_owner_cannot_touch_another_users_card(client):
    client.post("/v1/cards/linche/versions", json={"changes": {"name": "私有"}},
                headers={"Authorization": "Bearer 7"})
    assert _get(client, user="8").json() == {"role_id": "linche", "version": 0, "fields": {}, "lines": []}
    r = client.post("/v1/cards/linche/activate", json={"version": 1},
                    headers={"Authorization": "Bearer 8"})
    assert r.status_code == 404


def test_roles_are_independent(client):
    client.post("/v1/cards/linche/versions", json={"changes": {"name": "临澈"}},
                headers={"Authorization": "Bearer 7"})
    client.post("/v1/cards/sudai/versions", json={"changes": {"name": "苏黛"}},
                headers={"Authorization": "Bearer 7"})
    assert _get(client, "linche").json()["fields"]["name"] == "临澈"
    assert _get(client, "sudai").json()["fields"]["name"] == "苏黛"


def test_non_numeric_user_is_404(client):
    r = client.post("/v1/cards/linche/versions", json={"changes": {"name": "A"}},
                    headers={"Authorization": "Bearer alice"})
    assert r.status_code == 404


def test_effective_lines_come_from_renderer(client):
    client.post("/v1/cards/linche/versions", json={"changes": {"name": "小澈", "boundaries": ["不谈钱"]}},
                headers={"Authorization": "Bearer 7"})
    body = _get(client).json()
    assert body["lines"] == ["- 名字：小澈", "- 关系边界：不谈钱"]
