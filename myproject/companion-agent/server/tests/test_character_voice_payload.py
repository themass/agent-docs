"""客户端要显示「这个角色说话用谁的声音」：目录接口必须把 voice_ref 给出去。

背景（2026-11-20）：通话页要做一个音色 chip（`贴心女友` / `病娇姐姐`）。客户端那边
已经写好了解析（顶层 → data.voice_ref → extensions.vvv.voice_ref → data.extensions.vvv.voice_ref），
但**服务端从来没发过这个字段**——只有 `voice_available: bool`。客户端解析一个不存在的键，
chip 永远是空的名，而且不报错。这类「两边都觉得自己对了」的缺口只能靠这里守住。

两个约束：
1. 有音色就给 provider + voice_id；没有就给 null，客户端据此退回默认显示，而不是猜。
2. **不给 params**：那是账号侧的调参，客户端不需要。
"""

from __future__ import annotations

import pytest

from companion.agent.roles.card import from_v2_json
from companion.api.http.routers.characters import CharacterSummary, public_voice_ref, summarize


def _card(**overrides):
    data = {"name": "测试角色", "description": "一个人。",
            "extensions": {"vvv": {"voice_ref": {"provider": "volcengine",
                                                 "voice_id": "saturn_zh_female_x_tob"}}}}
    card = from_v2_json({"spec": "chara_card_v2", "spec_version": "2.0", "data": data})
    return card


# --- 取值 ------------------------------------------------------------------------

def test_a_card_with_a_voice_gets_provider_and_id():
    ref = public_voice_ref(_card())
    assert ref == {"provider": "volcengine", "voice_id": "saturn_zh_female_x_tob"}


def test_a_card_without_a_voice_gets_none_not_a_guess():
    """没有音色的角色不能编一个 id——客户端会照着它去显示一个不存在的声音。"""
    card = from_v2_json({"spec": "chara_card_v2", "spec_version": "2.0",
                         "data": {"name": "x", "description": "y"}})
    assert public_voice_ref(card) is None


def test_privider_defaults_when_the_card_omits_it():
    """只写了 voice_id 的卡（手写、迁移来的）仍然可用。"""
    card = from_v2_json({"spec": "chara_card_v2", "spec_version": "2.0",
                         "data": {"name": "x", "description": "y",
                                  "extensions": {"vvv": {"voice_ref": {"voice_id": "only_id_tob"}}}}})
    assert public_voice_ref(card) == {"provider": "volcengine", "voice_id": "only_id_tob"}


def test_params_are_not_exposed():
    """params 是账号侧的调参（语速之类），客户端不需要，公开出去只是把供应商配置摊开。"""
    card = from_v2_json({"spec": "chara_card_v2", "spec_version": "2.0",
                         "data": {"name": "x", "description": "y",
                                  "extensions": {"vvv": {"voice_ref": {
                                      "provider": "volcengine", "voice_id": "v_tob",
                                      "params": {"speed_ratio": 1.2, "emotion": "calm"}}}}}})
    ref = public_voice_ref(card)
    assert "params" not in ref
    assert set(ref) == {"provider", "voice_id"}


# --- 进得了 JSON ----------------------------------------------------------------

def test_the_summary_payload_carries_voice_ref():
    card = _card()
    payload = summarize("test", card).to_json()
    assert payload["voice_ref"] == {"provider": "volcengine", "voice_id": "saturn_zh_female_x_tob"}
    assert payload["voice_available"] is True


def test_the_payload_uses_null_rather_than_omitting_the_key():
    """缺键和无值在客户端是两种处理；这里固定用 null，客户端只要判空。"""
    payload = CharacterSummary(id="x", name="X", tagline="t").to_json()
    assert "voice_ref" in payload and payload["voice_ref"] is None


def test_mutating_the_payload_does_not_reach_back_into_the_summary():
    summary = summarize("test", _card())
    payload = summary.to_json()
    payload["voice_ref"]["voice_id"] = "tampered"
    assert summary.to_json()["voice_ref"]["voice_id"] == "saturn_zh_female_x_tob"


# --- 随包发布的卡 ---------------------------------------------------------------

@pytest.mark.parametrize("character_id", ["linche", "sudai"])
async def test_the_shipped_cards_are_visible_to_the_client(character_id):
    """这些是客户端音色 chip 的第一批真实数据；null 就意味着 chip 没东西可显示。"""
    from companion.paths import CHARACTERS_DIR
    from companion.service.roles.files import CharacterSource

    payload = summarize(character_id, await CharacterSource(CHARACTERS_DIR).load(character_id)).to_json()
    assert payload["voice_ref"] and payload["voice_ref"]["voice_id"]
    assert payload["voice_available"] is True


async def test_the_two_shipped_characters_expose_two_different_voices():
    """客户端要能看出两个角色不一样；相同的话 chip 换人不换名。"""
    from companion.paths import CHARACTERS_DIR
    from companion.service.roles.files import CharacterSource

    source = CharacterSource(CHARACTERS_DIR)
    ids = {summarize(cid, await source.load(cid)).to_json()["voice_ref"]["voice_id"]
           for cid in ("linche", "sudai")}
    assert len(ids) == 2
