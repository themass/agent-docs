from companion.text.events import (
    AVATAR_PROTOCOL_VERSION,
    strip_emotion_tags,
    to_avatar_events,
)


def test_leading_bracket_tag_stripped_and_surfaced():
    assert strip_emotion_tags("[joy]你好呀。") == ("你好呀。", ["joy"])


def test_inline_tags_stripped_from_text():
    assert strip_emotion_tags("我好想你[sad]今天下雨了。") == ("我好想你今天下雨了。", ["sad"])


def test_leading_fullwidth_paren_tag_stripped():
    assert strip_emotion_tags("（开心）今天见到你真高兴！") == ("今天见到你真高兴！", ["joy"])


def test_multiple_tags_deduped_in_order():
    clean, emotions = strip_emotion_tags("[joy]早。（开心）今天[sad]有点累。")
    assert clean == "早。今天有点累。"
    assert emotions == ["joy", "sad"]


def test_chinese_and_english_tags_map_to_same_emotion():
    assert strip_emotion_tags("[开心]嗯")[1] == ["joy"]
    assert strip_emotion_tags("[happy]嗯")[1] == ["joy"]


def test_unknown_tag_left_in_text():
    assert strip_emotion_tags("[unknown]内容") == ("[unknown]内容", [])
    assert strip_emotion_tags("（旁白）他笑了") == ("（旁白）他笑了", [])


def test_markdown_link_not_treated_as_tag():
    text = "看这个[link](https://example.com)吧。"
    assert strip_emotion_tags(text) == (text, [])


def test_text_without_tags_unchanged():
    text = "普通的一句话，前后有  空格。"
    assert strip_emotion_tags(text) == (text, [])
    assert strip_emotion_tags("") == ("", [])


def test_to_avatar_events_shape():
    events = to_avatar_events(["joy", "sad"], "speaking")
    assert events == [
        {"v": AVATAR_PROTOCOL_VERSION, "type": "emotion", "emotion": "joy"},
        {"v": AVATAR_PROTOCOL_VERSION, "type": "emotion", "emotion": "sad"},
        {"v": AVATAR_PROTOCOL_VERSION, "type": "state", "state": "speaking"},
    ]
    assert AVATAR_PROTOCOL_VERSION == 1


def test_to_avatar_events_empty():
    assert to_avatar_events(None, None) == []
    assert to_avatar_events([], "") == []
    assert to_avatar_events(["joy"], None) == [
        {"v": 1, "type": "emotion", "emotion": "joy"}
    ]


def test_strip_then_map_round_trip():
    clean, emotions = strip_emotion_tags("[joy]欢迎回来。")
    assert to_avatar_events(emotions, "idle")[0]["emotion"] == "joy"
    assert clean == "欢迎回来。"
