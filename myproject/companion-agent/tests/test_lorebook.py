"""世界书：从角色卡转换、关键词匹配（中英阿）、激活与预算。"""

from companion.domain.lorebook import LoreEntry, Lorebook, activate, from_character_book
from companion.domain.lorebook.text import matches, normalize


def _book(*entries: LoreEntry, scan_depth: int = 2) -> Lorebook:
    return Lorebook(entries=tuple(entries), scan_depth=scan_depth)


def test_character_book_conversion_reads_sillytavern_extensions():
    book = from_character_book({
        "scan_depth": 3,
        "entries": [
            {"id": 1, "keys": ["咖啡馆"], "content": "咖啡馆在街角。", "insertion_order": 50,
             "extensions": {"position": 4, "depth": 2, "role": 1}},
            {"id": 2, "keys": ["猫"], "content": "她养了一只橘猫。", "selective": True,
             "secondary_keys": ["名字"], "extensions": {"selectiveLogic": 3}},
            {"id": 3, "keys": ["x"], "content": "", "extensions": {}},             # 空内容：跳过
            {"id": 4, "keys": ["y"], "content": "作者注上方", "extensions": {"position": 2}},  # 不支持：按角色前
        ],
    })
    assert book is not None and book.scan_depth == 3
    by_uid = {e.uid: e for e in book.entries}
    assert set(by_uid) == {"1", "2", "4"}
    assert (by_uid["1"].position, by_uid["1"].depth, by_uid["1"].role, by_uid["1"].order) == ("at_depth", 2, "user", 50)
    assert by_uid["2"].secondary_keys == ("名字",) and by_uid["2"].logic == "and_all"
    assert by_uid["4"].position == "before_char" and book.unsupported == ("4",)


def test_cjk_keys_match_as_substrings_even_with_whole_word():
    text = normalize("我家的猫咪今天很乖")
    assert matches("猫", text, whole_word=True)


def test_latin_whole_word_respects_word_boundaries():
    text = normalize("I love cats")
    assert not matches("cat", text, whole_word=True)
    assert matches("cat", text, whole_word=False)
    assert matches("CATS", text, whole_word=True)   # 大小写折叠


def test_arabic_matching_ignores_diacritics_and_alef_forms():
    text = normalize("أُحِبُّ القَهْوَة")      # 带变音符、带 hamza 的 alef
    assert matches("احب", text)
    assert matches("القهوة", text)


def test_regex_keys_and_invalid_regex_never_match_badly():
    text = normalize("tomorrow at 3pm")
    assert matches("/\\d+pm/", text)
    assert not matches("/(unclosed/", text)


def test_activation_uses_primary_secondary_logic_and_constant():
    entries = [
        LoreEntry(uid="always", keys=(), content="世界观", constant=True, order=10),
        LoreEntry(uid="cat", keys=("猫",), content="橘猫叫阿橘", order=20),
        LoreEntry(uid="cat-name", keys=("猫",), secondary_keys=("名字",), logic="and_any", content="名字", order=30),
        LoreEntry(uid="not-dog", keys=("猫",), secondary_keys=("狗",), logic="not_any", content="没有狗", order=40),
        LoreEntry(uid="off", keys=("猫",), content="禁用", enabled=False),
    ]
    act = activate(_book(*entries), ["我的猫很可爱"], budget_chars=1000)
    assert [e.uid for e in act.entries] == ["always", "cat", "not-dog"]   # 输出按顺序号升序


def test_scan_depth_limits_which_messages_are_scanned():
    entry = LoreEntry(uid="old", keys=("灯塔",), content="灯塔的故事")
    recent = ["今天天气不错", "嗯", "上次说的灯塔"]
    assert activate(_book(entry, scan_depth=2), recent, budget_chars=100).entries == ()
    assert activate(_book(entry, scan_depth=3), recent, budget_chars=100).entries[0].uid == "old"


def test_budget_keeps_higher_order_entries_and_reports_the_dropped():
    entries = [
        LoreEntry(uid="low", keys=("a",), content="x" * 60, order=1),
        LoreEntry(uid="high", keys=("a",), content="y" * 60, order=99),
    ]
    act = activate(_book(*entries), ["a"], budget_chars=100)
    assert [e.uid for e in act.entries] == ["high"] and act.dropped == ("low",)
