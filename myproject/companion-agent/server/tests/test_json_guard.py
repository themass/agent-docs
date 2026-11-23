"""cue JSON 守卫：一行 {"say":…,"cues":[…]} 不能被断句器切碎。

生产日志里 `said='{"say":"好，其他都能进…` 的泄漏路径：prompt 要求模型输出一行
cue JSON，断句器却在 say 内部的句号、逗号与 200 字硬切处把它剁成碎片，每片都解不成
结构化片段，回落成原文——`{"say":"` 就进了字幕和 TTS。守卫在断句器前面把整行 JSON
缓住，等花括号闭合再整段下发。
"""

import pytest

from companion.agent.text.json_guard import CueJsonGuard
from companion.agent.text.splitter import SentenceSplitter

LINE = '{"say":"好，那先把能跑的部分跑起来。你现在是在哪个环节卡住了？","cues":[{"kind":"avatar.expression","name":"calm","anchor":"segment_start"}]}'


def guard():
    return CueJsonGuard(SentenceSplitter())


def test_whole_json_line_in_one_feed():
    out = guard().feed(LINE)
    assert out == [LINE]


def test_json_held_until_braces_close_across_chunks():
    g = guard()
    out = []
    step = 9
    for i in range(0, len(LINE), step):
        out += g.feed(LINE[i:i + step])
    # F16：say 在整对象闭合前经断句器放出；闭合后下发 cues 壳。
    assert any(s.startswith("好，那先把") for s in out)
    assert any("cues" in s for s in out)


def test_escaped_quotes_and_braces_in_say():
    blob = '{"say":"他说「{\\"嗯。\\"}」。","cues":[]}'
    g = guard()
    out = g.feed(blob[:12])
    assert out == []          # 引号里的 } 不算闭合
    out += g.feed(blob[12:])
    assert out == [blob]


def test_prose_before_json_keeps_order():
    g = guard()
    out = g.feed("你把报错贴给我。")     # 断句器会晚一块才吐这句
    out += g.feed('{"say":"好。","cues":[]}')
    out += g.flush()
    assert out == ["你把报错贴给我。", '{"say":"好。","cues":[]}']


def test_prose_without_ending_flushes_before_json():
    # "好的，" 没有终止符会被断句器扣住；JSON 到达时必须先把它放出来，
    # 否则念出来的顺序变成先 JSON 再"好的"。
    g = guard()
    out = g.feed('好的，{"say":"继续？","cues":[]}')
    assert out == ["好的，", '{"say":"继续？","cues":[]}']


def test_brace_that_is_not_json_goes_to_splitter():
    g = guard()
    out = g.feed("{不是协议 JSON。")
    out += g.flush()
    joined = "".join(out)
    assert "{不是协议" in joined


def test_unclosed_json_is_dropped_at_flush():
    g = guard()
    assert g.feed('{"say":"没写完的') == []
    assert g.flush() == []


def test_unclosed_json_over_cap_discards_rest_until_flush():
    g = CueJsonGuard(SentenceSplitter(), max_pending_chars=40)
    assert g.feed('{"say":"' + "很长很长" * 10) == []
    assert g._pending is None
    assert g.feed('剩余内容。","cues":[]}') == []
    assert g.flush() == []
    valid = '{"say":"继续。"}'
    assert g.feed(valid) == [valid]


@pytest.mark.parametrize("blob", [
    '{"say":"好。{"say":"继续。","cues":[]}',
    '{"say":123,"cues":[]}',
    '{"say":"好。",oops}',
    '{"say":"好。","cues":[]]',
    '{"say":"好。{\\"say\\":\\"继续。\\"}","cues":[]}',
])
@pytest.mark.parametrize("step", [1, 9, 1000])
def test_contaminated_cue_json_never_reaches_speech(blob, step):
    g = guard()
    out = []
    for i in range(0, len(blob), step):
        out += g.feed(blob[i:i + step])
    out += g.flush()
    assert out == []


def test_malformed_complete_object_does_not_drop_following_valid_fragment():
    g = guard()
    assert g.feed('{"say":123}' + LINE) + g.flush() == [LINE]


@pytest.mark.parametrize("blob", [
    '{"say":"好。{"say":"继续。","cues":[]}',
    '{"say":"未完成',
])
async def test_pipeline_never_yields_malformed_json(blob):
    from companion.agent.brain.fake import FakeBrain
    from companion.agent.brain.port import TurnRequest
    from companion.service.turn.pipeline import TurnPipeline

    pipeline = TurnPipeline(FakeBrain(list(blob)))
    request = TurnRequest(user_id="test", character_id="test", message="test")
    assert [item async for item in pipeline.run(request)] == []


def test_complete_over_cap_is_dropped_but_following_prose_survives():
    g = CueJsonGuard(SentenceSplitter(), max_pending_chars=40)
    blob = '{"say":"' + "长" * 50 + '"}'
    assert g.feed(blob + "正常正文。") + g.flush() == ["正常正文。"]


def test_two_json_objects_in_stream():
    g = guard()
    a = '{"say":"第一句。","cues":[]}'
    b = '{"say":"第二句。","cues":[]}'
    out = g.feed(a[:5]) + g.feed(a[5:] + b[:7]) + g.feed(b[7:])
    assert out == [a, b]


CUES_FIRST = '{"cues":[{"kind":"avatar.expression","name":"joy","anchor":"segment_start"}],"say":"你好呀。今天过得怎么样？"}'


def test_cues_first_object_is_recognized_as_protocol():
    """键序反过来也必须认作协议片段。

    守卫原先只认 `say` 开头的对象（`_PARTIAL_SHAPE` 只放行 s/sa/say）。模型把
    `cues` 写在前面时，前缀判定说"这不是片段"，于是整段回落断句器——`{"cues":[…`
    原文进字幕与 TTS，say 也被句号切成半句。语音 prompt 现在要求连续短片段，
    键序由模型决定，不能只认一种写法。
    """
    assert guard().feed(CUES_FIRST) == [CUES_FIRST]


def test_cues_first_object_holds_until_closed_when_chunked():
    """cues-first：外壳仍闭合才下发 JSON；say 可先流式。"""
    g = guard()
    out: list[str] = []
    for i in range(0, len(CUES_FIRST), 7):
        out += g.feed(CUES_FIRST[i:i + 7])
    out += g.flush()
    assert "你好呀。" in out
    assert any("cues" in s for s in out)


def test_a_bare_open_brace_still_holds_for_either_key():
    """只到 `{` / `{"` 时两把钥匙都可能，不能提前放行。"""
    assert guard().feed('{"c') == []
    assert guard().feed('{"cu') == []


@pytest.mark.parametrize("step", [3, 9])
def test_f16_say_streams_before_object_close(step):
    """长 cue JSON：首句不必等整条 JSON 闭合（F16 回归）。"""
    line = (
        '{"say":"你好呀。你连着摸了她好几次头，我还不知道她是谁呢，跟我说说呗。",'
        '"cues":[{"kind":"avatar.expression","name":"calm","anchor":"segment_start"}]}'
    )
    g = guard()
    first_sentence_at = None
    closed_at = None
    for i in range(0, len(line), step):
        emitted = g.feed(line[i : i + step])
        for idx, item in enumerate(emitted):
            if first_sentence_at is None and item.startswith("你好呀。"):
                first_sentence_at = i
            if closed_at is None and "cues" in item and item.startswith("{"):
                closed_at = i
    assert first_sentence_at is not None
    assert closed_at is not None
    assert first_sentence_at < len(line) - step


def test_prose_brace_that_is_not_a_fragment_still_passes():
    """放宽识别不等于放宽一切：`{"port"` 之类仍是正文。"""
    g = guard()
    out = g.feed('配置写成 {"port": 8081} 这样') + g.flush()
    assert out == ['配置写成 {"port": 8081} 这样']
