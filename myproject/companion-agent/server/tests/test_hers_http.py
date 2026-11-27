"""her 目录 HTTP 接口的响应形状：声明过的字段必须真的出得来。

同一个缺口发生过两次（voice_ref 见 test_character_voice_payload.py，renderer 见
test_characters_http.py）：内部 dataclass 的 to_json 给了字段、路由 response_model
没声明——FastAPI 把它滤掉，内部测试全绿而线上 JSON 里没有这个键。her 路由的每个
字段（renderer / status / pack_version / thumbnail / voice_ref / model_ref / effects…）
都由这里打真路由钉住。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.hers import build_router, HerCatalog
from companion.service.roles.hers import SqlHerPackStore


def _payload(name: str, **extra) -> dict:
    data = {
        "name": name,
        "tagline": "她",
        "model_ref": {"asset": "a-v1", "version": 1, "hash": "cd" * 32},
        "effects": [{"id": "fx_wave"}, {"id": "fx_pat_head"}],
        "stickers": [{"id": "st_star"}],
        "touch_zones": [{"id": "head", "rect": [0.4, 0.0, 0.6, 0.3]}],
        "thumbnail": "https://cdn/t.webp",
    }
    data.update(extra)
    return data


def _client(sqlite_engine) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(HerCatalog(SqlHerPackStore(sqlite_engine)),
                                    build_current_user(AllowAllVerifier())))
    return TestClient(app)


def _as() -> dict:
    return {"Authorization": "Bearer 1001"}


async def _seed(sqlite_engine) -> None:
    store = SqlHerPackStore(sqlite_engine)
    await store.upsert(her_id="live2d-linche-v1", renderer="live2d",
                       payload=_payload("林澈", voice_ref={"provider": "volcengine",
                                                          "voice_id": "v_linche",
                                                          "params": {"speed": 1.1}}),
                       status="published", source="card")
    await store.upsert(her_id="simple-plain", renderer="", payload=_payload("无判别"),
                       status="draft", source="manual")


async def test_list_response_carries_every_declared_field(sqlite_engine):
    await _seed(sqlite_engine)
    body = _client(sqlite_engine).get("/v1/hers", headers=_as()).json()
    by_id = {item["id"]: item for item in body["items"]}
    assert body["total"] == 2
    her = by_id["live2d-linche-v1"]
    assert her["renderer"] == "live2d"
    assert her["status"] == "published"
    assert her["pack_version"] == 1
    assert her["thumbnail"] == "https://cdn/t.webp"
    assert her["effect_count"] == 2 and her["sticker_count"] == 1


async def test_voice_ref_excludes_params_over_http(sqlite_engine):
    """卡/包里的 voice_ref.params 是账号侧调参——对外只给 provider 与 voice_id（同角色目录口径）。"""
    await _seed(sqlite_engine)
    body = _client(sqlite_engine).get("/v1/hers", headers=_as()).json()
    her = {item["id"]: item for item in body["items"]}["live2d-linche-v1"]
    assert her["voice_ref"] == {"provider": "volcengine", "voice_id": "v_linche"}


async def test_detail_carries_the_presentation_manifest(sqlite_engine):
    await _seed(sqlite_engine)
    body = _client(sqlite_engine).get("/v1/hers/live2d-linche-v1", headers=_as()).json()
    assert body["model_ref"]["asset"] == "a-v1"
    assert body["source"] == "card"
    assert [e["id"] for e in body["effects"]] == ["fx_wave", "fx_pat_head"]
    assert body["touch_zones"][0]["id"] == "head"


async def test_unknown_her_is_404_not_500(sqlite_engine):
    await _seed(sqlite_engine)
    resp = _client(sqlite_engine).get("/v1/hers/ghost", headers=_as())
    assert resp.status_code == 404


async def test_empty_registry_gives_empty_list_not_error(sqlite_engine):
    body = _client(sqlite_engine).get("/v1/hers", headers=_as()).json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}
