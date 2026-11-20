"""展示文本清洗器：把模型输出里的 cue 协议片段剥成 say，供落库与气泡使用。

根因（2026-11-20 用户报「文字消息里看到 say 字样」）：语音回合的 cue 片段只在
TTS 那一跳被 TurnPipeline 剥掉，**落库与推给文字端的是原始模型输出**——
`{"say":…,"cues":[…]}` 原文进了气泡与历史；下一次文字回合的模型又在线程历史里
看到自己写过协议 JSON，于是照抄。清洗必须发生在回合落库/发布这一层，
语音路径仍读原文（见 platform_brain 的 raw_delta）。

Ruling：情绪标签（[joy]/（开心））**不在这里剥**——那是语音 TTS 的关切（不该念出来），
文字气泡里它们是可读的舞台提示；本模块只消灭协议 JSON。
"""

from companion.agent.text.display_cleaner import DisplayTextCleaner


def _drain(c: DisplayTextCleaner, chunks: list[str]) -> str:
    out = "".join(c.feed(x) for x in chunks)
    return out + c.flush()


def test_plain_text_passes_through_byte_for_byte():
    c = DisplayTextCleaner()
    assert _drain(c, ["今天好累", "，休息一下吧。"]) == "今天好累，休息一下吧。"


def test_protocol_fragment_becomes_say_text():
    c = DisplayTextCleaner()
    line = '{"say":"好，那先把能跑的部分跑起来。","cues":[{"kind":"avatar.expression","name":"calm","anchor":"segment_start"}]}'
    assert _drain(c, [line]) == "好，那先把能跑的部分跑起来。"


def test_fragment_split_across_chunks_stays_clean():
    """模型 token 怎么切不该决定用户看到什么：9 字符一片地喂，协议字样也不许漏。"""
    c = DisplayTextCleaner()
    line = '{"say":"我在。","cues":[{"kind":"avatar.expression","name":"joy","anchor":"segment_end"}]}'
    chunks = [line[i:i + 9] for i in range(0, len(line), 9)]
    assert _drain(c, chunks) == "我在。"


def test_text_then_fragment_then_text_keeps_order():
    c = DisplayTextCleaner()
    assert _drain(c, ["你先说。", '{"say":"好。","cues":[]}', "，我记下了"]) == "你先说。好。，我记下了"


def test_emotion_tags_pass_through_untouched():
    """剥标签是语音管线的事；展示层保留它们（见模块文档的 Ruling）。"""
    c = DisplayTextCleaner()
    assert _drain(c, ["[joy]你来了。（旁白）今天怎么样？"]) == "[joy]你来了。（旁白）今天怎么样？"


def test_unknown_braces_are_regular_prose():
    c = DisplayTextCleaner()
    assert _drain(c, ['配置写成 {"port": 8081} 这样']) == '配置写成 {"port": 8081} 这样'


def test_incomplete_fragment_at_flush_never_resurfaces():
    """回合被截断：半截协议 JSON 宁可不显示，也不能把 `{"say":"` 漏进气泡。"""
    c = DisplayTextCleaner()
    out = "".join(c.feed(x) for x in ['好的。{"say":"这句不要', '显示到一半'])
    out += c.flush()
    assert '{"say"' not in out
    assert out.startswith("好的。")


def test_flush_resets_state_for_the_next_turn():
    c = DisplayTextCleaner()
    _drain(c, ['{"say":"上一轮'])          # 半截片段被丢
    assert _drain(c, ["新一轮。"]) == "新一轮。"


def test_feed_emits_plain_text_immediately():
    """聊天是流式的：非协议正文必须当帧吐出去，不许像断句器那样攒句。"""
    c = DisplayTextCleaner()
    assert c.feed("前面。") == "前面。"
    assert c.feed('{"say":"') == ""        # 疑似片段开头：扣住，等闭合
    closed = c.feed('好。","cues":[]}')     # 闭合
    assert closed == "好。"


def test_malformed_fragment_shaped_text_is_dropped_not_shown():
    """开头像协议片段但坏掉的，和语音路径同判：丢弃，绝不回落成原文。"""
    c = DisplayTextCleaner()
    out = _drain(c, ['{"say": 这不是字符串,}', "尾句"])
    assert '{"say"' not in out
    assert "尾句" in out
