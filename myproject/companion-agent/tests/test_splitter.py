from companion.domain.text.splitter import SentenceSplitter, split_sentences


def stream(chunks, *, max_chars=SentenceSplitter.DEFAULT_MAX_CHARS):
    """模拟 BrainTurn.tokens：逐块喂，最后 flush。"""
    s = SentenceSplitter(max_chars=max_chars)
    out = []
    for chunk in chunks:
        out.extend(s.feed(chunk))
    out.extend(s.flush())
    return out


def test_chinese_sentences():
    assert split_sentences("你好呀。我是晓雾！今天想聊点什么？") == [
        "你好呀。",
        "我是晓雾！",
        "今天想聊点什么？",
    ]


def test_english_sentences():
    assert split_sentences("Hello there. How are you? I am fine!") == [
        "Hello there.",
        "How are you?",
        "I am fine!",
    ]


def test_ellipsis_and_newline_end_sentences():
    assert split_sentences("让我想想……\n好的。") == ["让我想想……", "好的。"]


def test_closing_quote_stays_with_sentence():
    assert split_sentences("他说：“好的。”然后走了。") == ["他说：“好的。”", "然后走了。"]


def test_decimal_point_not_split():
    assert split_sentences("圆周率约等于 3.14159 呀。") == ["圆周率约等于 3.14159 呀。"]
    assert split_sentences("Price is 3.5 dollars. Fine.") == ["Price is 3.5 dollars.", "Fine."]
    assert split_sentences("Version 1.2.3 is out.") == ["Version 1.2.3 is out."]


def test_abbreviation_not_split():
    assert split_sentences("Mr. Smith is here.") == ["Mr. Smith is here."]
    assert split_sentences("Use e.g. this one. 然后呢？") == ["Use e.g. this one.", "然后呢？"]
    assert split_sentences("He left at 5 p.m. today.") == ["He left at 5 p.m. today."]


def test_long_run_without_punctuation_hits_cap():
    text = "啊" * 500
    parts = split_sentences(text, max_chars=200)
    assert [len(p) for p in parts] == [200, 200, 100]


def test_cap_prefers_comma():
    body = "嗯" * 190 + "，" + "嗯" * 100
    parts = split_sentences(body, max_chars=200)
    assert parts[0] == "嗯" * 190 + "，"
    assert parts[0][-1] == "，"


def test_flush_emits_remainder_without_terminator():
    s = SentenceSplitter()
    assert s.feed("还没说完") == []
    assert s.flush() == ["还没说完"]
    assert s.flush() == []


def test_feed_returns_nothing_until_terminator():
    s = SentenceSplitter()
    assert s.feed("你好") == []
    assert s.feed("呀") == []
    # 句号后面可能还跟着 "！" 或收尾引号，所以等下一个字符才定型
    assert s.feed("。") == []
    assert s.feed("我") == ["你好呀。"]


def test_repeating_terminator_absorbed_into_one_sentence():
    s = SentenceSplitter()
    assert s.feed("等等！") == []
    assert s.feed("！") == []
    assert s.feed("好") == ["等等！！"]


def test_streaming_chunk_boundaries_do_not_change_output():
    text = "你好呀。我是晓雾！今天想聊点什么？Price is 3.5 dollars. “好的。”嗯……"
    expected = split_sentences(text)
    for size in (1, 2, 3, 5, 7, 13):
        chunks = [text[i : i + size] for i in range(0, len(text), size)]
        assert stream(chunks) == expected, f"chunk size {size}"


def test_streaming_split_inside_terminator_sequence():
    # "！！" 与 "..." 可能被切在两块里
    assert stream(["等等！", "！"]) == ["等等！！"]
    assert stream(["好", ".", ".", "."]) == ["好..."]


def test_blank_output_dropped():
    assert split_sentences("你好。\n\n世界。") == ["你好。", "世界。"]
    assert split_sentences("   ") == []


def test_max_chars_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        SentenceSplitter(max_chars=0)
