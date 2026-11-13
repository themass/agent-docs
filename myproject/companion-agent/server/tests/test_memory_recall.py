"""词法召回（无向量、无模型）的离线测试。"""

from datetime import datetime

from companion.agent.memory.recall import features, rank

NOW = datetime(2026, 1, 1)


def test_chinese_single_character_and_word_queries_hit():
    items = [("tea", "喜欢喝茶", NOW), ("interview", "在准备面试", NOW), ("coffee", "喜欢咖啡", NOW)]
    assert rank("茶", items, 5) == ["tea"]
    assert rank("面试", items, 5) == ["interview"]
    assert rank("咖啡", items, 5) == ["coffee"]


def test_a_word_does_not_match_an_unrelated_memory():
    items = [("tea", "喜欢喝茶", NOW)]
    assert rank("火箭", items, 5) == []


def test_english_and_arabic_are_split_on_words():
    assert {"tea", "coffee"} <= features("I like tea, and coffee!")
    assert features("أحب الشاي") == {"أحب", "الشاي"}
    items = [("en", "tea time tomorrow", NOW)]
    assert rank("tea", items, 5) == ["en"]


def test_more_matching_terms_rank_higher():
    items = [("partial", "喝茶", NOW), ("full", "喜欢喝茶", datetime(2025, 1, 1))]
    assert rank("喜欢喝茶", items, 5) == ["full", "partial"]


def test_equal_scores_put_the_newer_memory_first():
    items = [("old", "喜欢喝茶", datetime(2025, 1, 1)), ("new", "喜欢喝茶", datetime(2026, 6, 1))]
    assert rank("喜欢喝茶", items, 5) == ["new", "old"]


def test_limit_is_respected():
    items = [(str(i), "喝茶", NOW) for i in range(10)]
    assert len(rank("茶", items, 3)) == 3
