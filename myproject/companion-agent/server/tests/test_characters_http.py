"""角色目录 HTTP 接口的响应形状：声明过的字段必须真的出得来。

背景（2026-11-27）：`CharacterSummary.to_json()` 给了 `renderer`（引擎判别），
但路由的 `response_model` 没声明这个字段——FastAPI 会把它滤掉。
`summarize` 与 `to_json` 的测试全绿，HTTP 响应里却没有这个键：「两边都觉得自己对了」
的缺口第二次出现（第一次是 voice_ref，见 test_character_voice_payload.py 的文件头）。
所以这里用真路由打真 HTTP，钉的是「到了线上 JSON 里」这一层，而不是内部对象。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.agent.roles.card import from_v2_json
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.characters import build_router, CharacterCatalog


def _card(name: str, model_ref) -> dict:
    data = {"name": name, "description": "一个人。"}
    if model_ref is not None:
        data["model_ref"] = model_ref
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


class _Source:
    """最小角色来源替身：整目录一次给全（与链的 cards() 同形）。"""

    def __init__(self, cards: dict[str, dict]):
        self._cards = {cid: from_v2_json(payload) for cid, payload in cards.items()}

    async def cards(self):
        return dict(self._cards)


def _client(cards: dict[str, dict]) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(CharacterCatalog(_Source(cards)),
                                    build_current_user(AllowAllVerifier())))
    return TestClient(app)


_CARDS = {
    "linche": _card("林澈", {"renderer": "simple", "asset": "linche-v1"}),
    "plain": _card("无判别", None),
}


def _as(user: str = "u1") -> dict:
    # /v1 的 owner id 是数字（BIGINT），与 test_api_routes 的约定一致。
    return {"Authorization": "Bearer 1001"}


def test_list_response_carries_the_renderer_in_http_json():
    body = _client(_CARDS).get("/v1/characters", headers=_as()).json()
    by_id = {item["id"]: item for item in body["items"]}
    assert by_id["linche"]["renderer"] == "simple"


def test_detail_response_carries_the_renderer_too():
    body = _client(_CARDS).get("/v1/characters/linche", headers=_as()).json()
    assert body["renderer"] == "simple"


def test_a_card_without_a_discriminator_gives_empty_string_not_a_missing_key():
    """缺键与空串在客户端是两种处理；这里固定空串 = 「卡没声明」，客户端退回默认引擎。"""
    body = _client(_CARDS).get("/v1/characters/plain", headers=_as()).json()
    assert "renderer" in body and body["renderer"] == ""
    listed = {item["id"]: item for item in _client(_CARDS).get("/v1/characters", headers=_as()).json()["items"]}
    assert "renderer" in listed["plain"] and listed["plain"]["renderer"] == ""
