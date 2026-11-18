"""双路径摄入：结构化 say+cues 优先，标签回落（P3 / v1 §7.1）。"""

from __future__ import annotations

from companion.agent.protocol.fragment import from_tags, ingest, try_parse_fragment


def test_structured_fragment_maps_cues_and_anchors():
    text = (
        '{"say":"怎么啦？我在听。","cues":['
        '{"kind":"avatar.expression","name":"warm_smile",'
        '"params":{"intensity":0.4},"anchor":"segment_start"}]}'
    )
    frag = try_parse_fragment(text)
    assert frag is not None
    assert frag.source == "structured"
    assert frag.say == "怎么啦？我在听。"
    assert len(frag.intents) == 1
    intent = frag.intents[0]
    assert intent.kind == "emotion"
    assert intent.name == "warm_smile"
    assert intent.phase == "start"
    assert intent.params["intensity"] == 0.4


def test_bad_cue_keeps_say_and_counts_drop():
    text = '{"say":"还在。","cues":[{"kind":"nope","name":"x"},{"kind":"emotion","name":"joy"}]}'
    frag = try_parse_fragment(text)
    assert frag is not None
    assert frag.say == "还在。"
    assert [i.name for i in frag.intents] == ["joy"]
    assert frag.dropped_cues == 1


def test_non_json_falls_back_to_tags():
    frag = ingest("[joy]你好呀（开心）")
    assert frag.source == "tag"
    assert "[joy]" not in frag.say and "（开心）" not in frag.say
    # strip_emotion_tags 把中英文都归一成 joy
    assert [i.name for i in frag.intents] == ["joy"]
    assert all(i.kind == "emotion" and i.phase == "start" for i in frag.intents)


def test_ingest_prefers_structured_over_tags():
    text = '{"say":"[joy]不会当正文标签","cues":[]}'
    frag = ingest(text)
    assert frag.source == "structured"
    assert frag.say == "[joy]不会当正文标签"
    assert frag.intents == ()


def test_from_tags_empty_when_no_markers():
    frag = from_tags("普通一句话。")
    assert frag.say == "普通一句话。"
    assert frag.intents == ()
    assert frag.source == "tag"


def test_segment_end_anchor_maps_to_after():
    text = '{"say":"好","cues":[{"kind":"gesture","name":"nod","anchor":"segment_end"}]}'
    frag = try_parse_fragment(text)
    assert frag is not None
    assert frag.intents[0].kind == "gesture"
    assert frag.intents[0].phase == "after"
