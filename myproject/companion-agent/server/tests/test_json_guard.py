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
    assert out == [] or out == [LINE]
    if not out:
        out = g.feed("") + g.flush()
    assert out == [LINE]


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


def test_unclosed_json_still_delivered_at_flush():
    g = guard()
    out = g.feed('{"say":"没写完的')
    assert out == []
    out += g.flush()
    assert "".join(out) == '{"say":"没写完的'


def test_unclosed_json_over_cap_releases_to_splitter():
    # 跑偏的长 JSON 超过上限必须脱手（回落断句器），不能永远扣在守卫里。
    g = CueJsonGuard(SentenceSplitter(), max_pending_chars=40)
    blob = '{"say":"' + "很长很长" * 10
    out = g.feed(blob)
    assert g._pending is None
    out += g.flush()
    assert "".join(out) == blob


def test_two_json_objects_in_stream():
    g = guard()
    a = '{"say":"第一句。","cues":[]}'
    b = '{"say":"第二句。","cues":[]}'
    out = g.feed(a[:5]) + g.feed(a[5:] + b[:7]) + g.feed(b[7:])
    assert out == [a, b]
