import pytest

from companion.adapters.memory.fake import InMemoryMemoryPort
from companion.ports.memory import MemoryItem, MemoryKind
from companion.ports.memory import coerce_kind


def item(content, *, kind=MemoryKind.FACT, character="xiaowu", message="m1", **kw):
    return MemoryItem(
        id=kw.pop("id", ""),
        content=content,
        kind=kind,
        source_character_id=character,
        source_message_id=message,
        **kw,
    )


async def test_add_search_and_list_roundtrip():
    port = InMemoryMemoryPort()
    stored = await port.add("u1", [item("用户养了一只叫团子的猫")])
    assert stored[0].id.startswith("mem-")
    assert stored[0].score is None

    hits = await port.search("u1", "团子最近怎么样", limit=5)
    assert [h.content for h in hits] == ["用户养了一只叫团子的猫"]
    assert hits[0].score > 0

    listed = await port.list_for_user("u1")
    assert [i.content for i in listed] == ["用户养了一只叫团子的猫"]


async def test_search_without_overlap_returns_nothing():
    port = InMemoryMemoryPort()
    await port.add("u1", [item("用户是程序员")])
    assert await port.search("u1", "今天天气如何") == []


async def test_user_isolation():
    port = InMemoryMemoryPort()
    await port.add("u1", [item("u1 的秘密", message="m-u1")])
    await port.add("u2", [item("u2 的秘密", message="m-u2")])

    assert [i.content for i in await port.list_for_user("u2")] == ["u2 的秘密"]
    assert await port.list_for_user("u1") == await port.list_for_user("u1")
    # 用一个必定命中的词也看不到别人的条目
    hits = await port.search("u2", "秘密")
    assert {h.content for h in hits} == {"u2 的秘密"}


async def test_cross_character_read_preserves_source():
    port = InMemoryMemoryPort()
    await port.add("u1", [item("用户喜欢下雨天", character="xiaowu", message="m-1")])
    await port.add("u1", [item("用户讨厌香菜", character="afei", message="m-2")])

    # 同一用户，另一个角色照样读得到，并带回来源
    hits = await port.search("u1", "下雨天")
    assert hits[0].source_character_id == "xiaowu"
    assert hits[0].source_message_id == "m-1"

    listed = await port.list_for_user("u1")
    assert {i.source_character_id for i in listed} == {"xiaowu", "afei"}


async def test_delete_one_only_removes_that_item():
    port = InMemoryMemoryPort()
    stored = await port.add("u1", [item("第一条"), item("第二条")])

    assert await port.delete_one("u1", stored[0].id) is True
    assert [i.content for i in await port.list_for_user("u1")] == ["第二条"]

    assert await port.delete_one("u1", stored[0].id) is False
    assert await port.delete_one("u1", "mem-unknown") is False


async def test_delete_one_cannot_touch_another_users_item():
    port = InMemoryMemoryPort()
    (mine,) = await port.add("u2", [item("u2 的条目")])
    assert await port.delete_one("u1", mine.id) is False
    assert port.raw_count("u2") == 1


async def test_delete_user_leaves_zero_residue_and_spares_others():
    port = InMemoryMemoryPort()
    await port.add("u1", [item("a"), item("b")])
    await port.add("u2", [item("c")])

    assert await port.delete_user("u1") == 2
    assert await port.list_for_user("u1") == []
    assert await port.search("u1", "a") == []
    assert port.raw_count("u1") == 0
    assert port.raw_count("u2") == 1

    assert await port.delete_user("u1") == 0


async def test_list_paginates_newest_first():
    port = InMemoryMemoryPort()
    stored = await port.add("u1", [item(f"第{i}条") for i in range(5)])
    page = await port.list_for_user("u1", limit=2, offset=0)
    assert len(page) == 2
    # 同一批写入时间戳可能相同，用 id 集合确认分页切片生效
    all_ids = [i.id for i in await port.list_for_user("u1")]
    assert [i.id for i in page] == all_ids[:2]
    assert set(all_ids) == {i.id for i in stored}


async def test_added_items_are_copies_not_aliases():
    port = InMemoryMemoryPort()
    source = item("可变对象")
    stored = await port.add("u1", [source])
    stored[0].content = "被外部改掉"
    assert (await port.list_for_user("u1"))[0].content == "可变对象"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FACT", MemoryKind.FACT),
        (" preference ", MemoryKind.PREFERENCE),
        ("event", MemoryKind.EVENT),
        ("事件", MemoryKind.EVENT),
        ("偏好", MemoryKind.PREFERENCE),
        ("nonsense", None),
        (None, None),
    ],
)
def test_coerce_kind(raw, expected):
    assert coerce_kind(raw) is expected
