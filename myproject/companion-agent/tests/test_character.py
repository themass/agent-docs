import pytest

from companion.prompt.character import (
    PERSONA_MAX_CHARS,
    CharacterFormatError,
    from_v2_json,
    render_persona,
    to_v2_json,
)

V2_CARD = {
    "spec": "chara_card_v2",
    "spec_version": "2.0",
    "data": {
        "name": "晓雾",
        "description": "住在山顶灯塔里的图书管理员，喜欢在雾天整理旧书。",
        "personality": "安静、耐心，偶尔尖锐；对书里的故事比对人有耐心。",
        "scenario": "深夜的灯塔图书馆，窗外起雾，你敲门借书。",
        "first_mes": "门没锁。……你身上有雨味。",
        "mes_example": "<START>\n{{user}}: 这里还开着吗？\n{{char}}: 开。反正我也不睡。",
        "creator_notes": "内部官方角色",
        "tags": ["治愈", "图书馆"],
        "voice_ref": {"provider": "volcengine", "voice_id": "v-xiaowu"},
        "model_ref": "default-chat",
        "emotion_map": {"neutral": "neutral.png", "smile": "smile.png"},
        "memory_policy": {"scope": "user", "cross_character": True},
        "extensions": {"companion": {"version": 1}},
        "system_prompt": "始终用中文。",
        "post_history_instructions": "保持简短。",
        "alternate_greetings": ["雾太大了，图书馆今天不开。……不过你可以进来。"],
    },
}


def test_v2_reads_core_fields():
    card = from_v2_json(V2_CARD)
    assert card.id == ""
    assert card.name == "晓雾"
    assert card.tags == ["治愈", "图书馆"]
    assert card.voice_ref == {"provider": "volcengine", "voice_id": "v-xiaowu"}
    assert card.emotion_map["smile"] == "smile.png"
    assert card.memory_policy["cross_character"] is True
    assert card.first_mes.startswith("门没锁")
    assert card.is_v3 is False


def test_v2_round_trip_preserves_everything_read():
    original = from_v2_json(V2_CARD)
    again = from_v2_json(to_v2_json(original))
    assert again == original


def test_v2_round_trip_keeps_unknown_keys_in_extensions():
    payload = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "林澈",
            "description": "d",
            "personality": "p",
            "scenario": "s",
            "first_mes": "f",
            "mes_example": "",
            "custom_field": {"nested": [1, 2]},
            "extensions": {"depth_prompt": {"depth": 4}},
        },
    }
    card = from_v2_json(payload)
    assert card.extensions["custom_field"] == {"nested": [1, 2]}
    assert card.extensions["depth_prompt"] == {"depth": 4}

    exported = to_v2_json(card)
    assert exported["data"]["extensions"]["custom_field"] == {"nested": [1, 2]}
    assert exported["data"]["extensions"]["depth_prompt"] == {"depth": 4}


def test_v3_import_maps_data_block_and_archives_extras():
    payload = {
        "spec": "chara_card_v3",
        "spec_version": "3.0",
        "data": {
            "name": "小遥",
            "description": "海边民宿的老板。",
            "personality": "话多、热情",
            "scenario": "海风很大的下午",
            "nickname": "小遥",
            "creator_notes_multilingual": {"zh": "官方角色"},
            "group_only_greetings": ["大家好。"],
            "source": ["https://example.invalid/card"],
            "assets": [
                {"type": "icon", "uri": "ccdefault:", "name": "main"},
                {"type": "emotion", "uri": "embeded://smile.png", "name": "smile"},
                {"type": "emotion", "uri": "embeded://sad.png", "name": "sad"},
            ],
        },
    }
    card = from_v2_json(payload)
    assert card.name == "小遥"
    assert card.is_v3 is True
    # V3 的 emotion 资源映射到 emotion_map，icon 不算
    assert card.emotion_map == {"smile": "embeded://smile.png", "sad": "embeded://sad.png"}
    # V3 新字段落到 extensions["vvv"]，不散在 extensions 顶层
    assert card.extensions["vvv"]["nickname"] == "小遥"
    assert card.extensions["vvv"]["assets"]
    assert "nickname" not in card.extensions

    exported = to_v2_json(card)
    assert exported["spec"] == "chara_card_v2"
    assert exported["data"]["extensions"]["vvv"]["creator_notes_multilingual"] == {"zh": "官方角色"}
    assert exported["data"]["emotion_map"]["smile"] == "embeded://smile.png"


def test_rejects_payload_without_data_block():
    with pytest.raises(CharacterFormatError):
        from_v2_json({"spec": "chara_card_v2"})
    with pytest.raises(CharacterFormatError):
        from_v2_json({"spec": "chara_card_v2", "data": []})


def test_render_persona_includes_name_personality_scenario():
    text = render_persona(from_v2_json(V2_CARD))
    assert "晓雾" in text
    assert "安静、耐心" in text
    assert "深夜的灯塔图书馆" in text
    # 例子对话属于另一段提示词，不该混进人设
    assert "{{char}}" not in text


def test_render_persona_stays_under_limit():
    payload = {
        "spec": "chara_card_v2",
        "data": {
            "name": "长卡",
            "description": "描" * 5000,
            "personality": "性" * 5000,
            "scenario": "景" * 5000,
        },
    }
    text = render_persona(from_v2_json(payload))
    assert len(text) <= PERSONA_MAX_CHARS
    # 截断也要保住每段的标题，否则看不出被砍掉的是什么
    for title in ("角色描述", "性格", "场景"):
        assert title in text


def test_render_persona_handles_empty_card():
    assert render_persona(from_v2_json({"spec": "chara_card_v2", "data": {}})) == "你正在扮演「这个角色」。"
