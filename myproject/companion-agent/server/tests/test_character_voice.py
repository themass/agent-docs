"""音色跟着角色走：一间房一个说话人，不是一台 worker 一个嗓子。

背景（2026-11-20，真机）：林澈和苏黛各自语音聊天，两个人是同一个声音。成因是两层叠加：

1. **卡里的音色从来没被读出来**。仓库自带的卡把 ``voice_ref`` 写在 ``extensions.vvv`` 下
   （见 ``agent/characters/README.md``），而 ``from_v2_json`` 只读 ``data.voice_ref``，
   于是每一张卡都是 ``voice_ref=None``，全库角色都被当成「没有声音」。
2. **就算读出来也没人用**。``build_voice_stack()`` 不接参数，音色只从环境变量
   ``COMPANION_VOICE_ID`` / ``VOLC_TTS_VOICE`` 来——进程级配置，一个 worker 上所有房间共用一个。

这里按「卡 → 房间 → TTS」三段分别断言，最后一段是端到端的：两个角色进两个房间，
拿到的是两个不同的说话人。中间任何一环断开，最后那条都会红。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from companion.agent.roles.card import from_v2_json
from companion.api.livekit.entrypoint import RoomIdentity, build_session_options, room_voice_id
from companion.bootstrap.voice_stack import VoiceStackConfig, resolve_voice_id

# --- 第一段：卡里的音色必须真的被读出来 ---------------------------------------------

def _card(voice_ref: dict[str, Any] | None, *, at: str = "vvv") -> dict[str, Any]:
    data: dict[str, Any] = {"name": "测试角色", "description": "一个人。"}
    if voice_ref is not None:
        if at == "vvv":
            data["extensions"] = {"vvv": {"voice_ref": voice_ref}}
        else:
            data["voice_ref"] = voice_ref
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


def test_voice_ref_is_read_from_the_platform_extension_block():
    """仓库自带的卡都写在这里。只读 data 顶层的话，全库角色都没有声音。"""
    card = from_v2_json(_card({"provider": "volcengine", "voice_id": "saturn_zh_female_x_tob"}))
    assert card.voice_ref == {"provider": "volcengine", "voice_id": "saturn_zh_female_x_tob"}


def test_a_standard_v2_card_with_a_top_level_voice_ref_still_works():
    """外部导入的卡按 V2 规范写在 data 顶层。不能为了修我们自己的卡把它读丢。"""
    card = from_v2_json(_card({"provider": "volcengine", "voice_id": "top_level_tob"}, at="top"))
    assert card.voice_ref == {"provider": "volcengine", "voice_id": "top_level_tob"}


def test_the_top_level_field_wins_when_both_exist():
    """两份都有时认顶层：那是 V2 规范的位置，也是导入导出会写回的位置。"""
    card = from_v2_json({
        "spec": "chara_card_v2", "spec_version": "2.0",
        "data": {"name": "x", "description": "y",
                 "voice_ref": {"provider": "volcengine", "voice_id": "outer_tob"},
                 "extensions": {"vvv": {"voice_ref": {"provider": "volcengine", "voice_id": "inner_tob"}}}},
    })
    assert card.voice_ref["voice_id"] == "outer_tob"


def test_a_card_without_a_voice_is_not_an_error():
    assert from_v2_json(_card(None)).voice_ref is None


@pytest.mark.parametrize("character_id", ["linche", "sudai"])
async def test_the_shipped_cards_actually_declare_an_usable_speaker(character_id):
    """随包发布的卡是这条链路的第一环。它们没有 voice_ref 时，后面全部逻辑都是空转。"""
    from companion.paths import CHARACTERS_DIR
    from companion.service.roles.files import CharacterSource

    card = await CharacterSource(CHARACTERS_DIR).load(character_id)
    assert card.voice_ref and card.voice_ref.get("voice_id"), f"{character_id} 没有音色"


async def test_the_two_shipped_characters_do_not_share_one_voice():
    """验收条件本身：两个角色必须是两个说话人。"""
    from companion.paths import CHARACTERS_DIR
    from companion.service.roles.files import CharacterSource

    source = CharacterSource(CHARACTERS_DIR)
    voices = {cid: (await source.load(cid)).voice_ref["voice_id"] for cid in ("linche", "sudai")}
    assert len(set(voices.values())) == 2, f"两个角色共用一个声音：{voices}"


# --- 第二段：房间 → 说话人 ---------------------------------------------------------

class _Chars:
    """最小的角色卡来源替身。"""

    def __init__(self, by_id: dict[str, str | None], *, broken: bool = False):
        self._by_id, self._broken = by_id, broken

    async def load(self, character_id: str) -> Any:
        if self._broken:
            raise FileNotFoundError(character_id)
        voice = self._by_id[character_id]
        return type("Card", (), {"voice_ref": {"voice_id": voice} if voice else None})()


def _identity(character_id: str) -> RoomIdentity:
    return RoomIdentity(user_id="1002", character_id=character_id, chat_session_id=42)


async def test_each_room_resolves_its_own_character_voice():
    chars = _Chars({"linche": "a_tob", "sudai": "b_tob"})
    assert await room_voice_id(_identity("linche"), chars) == "a_tob"
    assert await room_voice_id(_identity("sudai"), chars) == "b_tob"


async def test_a_card_without_a_voice_falls_through_instead_of_raising():
    """没有音色的卡退回默认值，不是拒绝入场：人设与历史都还按这个角色走。"""
    assert await room_voice_id(_identity("x"), _Chars({"x": None})) is None


async def test_an_unreadable_card_does_not_take_the_room_down():
    """卡是发布资产，读盘失败不该让房间连不上。只有音色退回默认。"""
    assert await room_voice_id(_identity("x"), _Chars({}, broken=True)) is None


async def test_no_character_source_means_the_default_voice():
    assert await room_voice_id(_identity("linche"), None) is None


# --- 第三段：说话人真的传到了语音栈 -----------------------------------------------

class _Factory:
    """记录被问到的说话人，返回三个占位零件。"""

    def __init__(self):
        self.asked: list[str | None] = []

    def __call__(self, voice_id: str | None = None):
        self.asked.append(voice_id)
        return (object(), object(), object())


def test_the_room_voice_reaches_the_tts_factory():
    factory = _Factory()
    build_session_options(mode="voice", voice_factory=factory, voice_id="a_tob")
    assert factory.asked == ["a_tob"]


def test_text_mode_never_builds_a_voice_stack():
    factory = _Factory()
    build_session_options(mode="text", voice_factory=factory, voice_id="a_tob")
    assert factory.asked == []


def test_a_factory_that_takes_no_arguments_still_works():
    """离线脚本与老调用方传的是无参函数。不能因为新增了参数就让它们炸掉。"""
    called = []
    options = build_session_options(mode="voice", voice_factory=lambda: (called.append(1), (object(), object()))[1],
                                    voice_id=None)
    assert called and options["tts"] is not None


async def test_two_rooms_with_two_characters_ask_for_two_voices():
    """端到端：两个角色进两个房间，语音栈收到两个不同的说话人。"""
    factory = _Factory()
    chars = _Chars({"linche": "a_tob", "sudai": "b_tob"})
    for character_id in ("linche", "sudai"):
        build_session_options(mode="voice", voice_factory=factory,
                              voice_id=await room_voice_id(_identity(character_id), chars))
    assert factory.asked == ["a_tob", "b_tob"]


# --- 说话人的兜底顺序 ---------------------------------------------------------------

def test_the_card_voice_wins():
    cfg = VoiceStackConfig(voice_id="env_voice_tob", enabled=True)
    assert resolve_voice_id(card_voice="card_tob", config=cfg) == "card_tob"


def test_without_a_card_voice_the_environment_value_is_used():
    cfg = VoiceStackConfig(voice_id="env_voice_tob", enabled=True)
    assert resolve_voice_id(card_voice=None, config=cfg) == "env_voice_tob"


def test_blank_values_are_skipped_not_used(monkeypatch):
    monkeypatch.setenv("VOLC_TTS_VOICE", "")
    cfg = VoiceStackConfig(voice_id="  ", enabled=True)
    assert resolve_voice_id(card_voice="  ", config=cfg) == "saturn_zh_female_keainvsheng_tob"


def test_the_card_voice_is_what_the_built_tts_gets(monkeypatch):
    """装配出来的 TTS 上真的带着那个音色——不是只传到一个没被用的参数里。"""
    pytest.importorskip("livekit.agents")
    from companion.bootstrap.voice_stack import build_tts

    tts = build_tts(VoiceStackConfig(voice_id="env_voice_tob", enabled=True), voice_id="card_tob")
    # 说话人落在插件的 options 上，最终进请求体的 ``req_params.speaker``；
    # ``tts.model`` 是基类的 "unknown"，不是这里要看的东西。
    assert tts._opts.voice == "card_tob"


def test_the_qa_record_carries_the_room_voice_not_the_global_one():
    """质检里记的音色必须等于实际出声的那个，否则「她当时是什么声音」事后没法查。"""
    from companion.bootstrap.voice_wiring import voice_wiring

    wiring = voice_wiring({"tts_provider": "volcengine", "tts_voice": "global_tob"})
    assert wiring.info_for("card_tob")["tts_voice"] == "card_tob"
    assert wiring.info_for(None)["tts_voice"] == "global_tob"


def test_the_wiring_hands_the_room_voice_to_the_recorder():
    from types import SimpleNamespace

    from companion.bootstrap.voice_wiring import voice_wiring

    platform = SimpleNamespace(qa=object(), compliance=object(), objects=None, tos_key_prefix="",
                               qa_enabled=True, chat=SimpleNamespace(submit=object(), control=object()))
    parts = voice_wiring({"tts_provider": "volcengine", "tts_voice": "global_tob"})(platform, "card_tob")
    assert parts.brain is not None
