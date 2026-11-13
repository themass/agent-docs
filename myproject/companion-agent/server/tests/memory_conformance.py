"""记忆接口一致性检查（规范 docs/chat-agent-memory-spec.md §9.1）。

任何后端只要通过 ``check_port`` 的全部断言，就满足规范 v1。每次检查使用新的随机用户，
不会与其他数据互相干扰，因此可以指向共享的真实存储。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from companion.agent.memory.port import (
    MAX_BATCH,
    MAX_CONTENT_CHARS,
    MAX_LIST_LIMIT,
    MAX_SEARCH_LIMIT,
    MemoryInvalid,
    MemoryItem,
    MemoryKind,
)


def _user(prefix: str = "conf") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _item(content: str, *, kind: MemoryKind = MemoryKind.FACT, at: datetime | None = None,
          item_id: str = "") -> MemoryItem:
    return MemoryItem(id=item_id, content=content, kind=kind, source_character_id="linche",
                      source_message_id="m1", created_at=at or datetime.now(UTC))


async def check_isolation(port) -> None:
    """§5.1、§6.2：不同用户互不可见；跨用户删除返回 False。"""
    alice, bob = _user("alice"), _user("bob")
    [a] = await port.add(alice, [_item("喜欢喝茶")])
    await port.add(bob, [_item("喜欢咖啡")])
    assert [i.content for i in await port.list_for_user(alice, limit=10)] == ["喜欢喝茶"]
    assert [i.content for i in await port.list_for_user(bob, limit=10)] == ["喜欢咖啡"]
    assert [i.content for i in await port.search(bob, "茶", limit=5)] == []
    assert await port.delete_one(bob, a.id) is False
    assert len(await port.list_for_user(alice, limit=10)) == 1
    await port.delete_user(alice)
    await port.delete_user(bob)


async def check_write_roundtrip(port) -> None:
    """§2、§7.1、§7.4：写入后立即可读；字段原样保存；id 与 created_at 由后端确认。"""
    user = _user()
    [stored] = await port.add(user, [_item("在准备面试", kind=MemoryKind.EVENT)])
    assert stored.id, "backend must assign a non-empty id"
    assert stored.kind == MemoryKind.EVENT
    assert stored.source_character_id == "linche" and stored.source_message_id == "m1"
    assert stored.score is None
    rows = await port.list_for_user(user, limit=10)
    assert [r.id for r in rows] == [stored.id]
    assert rows[0].content == "在准备面试" and rows[0].kind == MemoryKind.EVENT
    await port.delete_user(user)


async def check_validation(port) -> None:
    """§2.1、§3、§7.2：调用方错误抛 MemoryInvalid，且整批不写入。"""
    user = _user()
    for bad in ["", "   ", "x" * (MAX_CONTENT_CHARS + 1)]:
        try:
            await port.add(user, [_item(bad)])
        except MemoryInvalid:
            pass
        else:
            raise AssertionError(f"content {bad[:5]!r}... must be rejected")
    try:
        await port.add(user, [_item("ok")] * (MAX_BATCH + 1))
    except MemoryInvalid:
        pass
    else:
        raise AssertionError("batch over the limit must be rejected")
    assert await port.list_for_user(user, limit=10) == []
    await port.delete_user(user)


async def check_atomic_and_no_overwrite(port) -> None:
    """§7.1、§7.3：重复 id 拒绝，且同批其他条目不写入（原子）。"""
    user = _user()
    [first] = await port.add(user, [_item("第一条")])
    try:
        await port.add(user, [_item("新的一条"), _item("冲突", item_id=first.id)])
    except MemoryInvalid:
        pass
    else:
        raise AssertionError("a duplicate id must be rejected")
    assert [i.content for i in await port.list_for_user(user, limit=10)] == ["第一条"]
    await port.delete_user(user)


async def check_list_order_and_paging(port) -> None:
    """§4.1、§4.2、§4.3：created_at 倒序、同时间按 id 倒序；分页无重复无遗漏；limit 截断。"""
    user = _user()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    items = [_item(f"条目{i}", at=base + timedelta(minutes=i)) for i in range(5)]
    await port.add(user, items)
    all_rows = await port.list_for_user(user, limit=MAX_LIST_LIMIT)
    assert [r.content for r in all_rows] == [f"条目{i}" for i in reversed(range(5))]
    paged, offset = [], 0
    while True:
        window = await port.list_for_user(user, limit=2, offset=offset)
        if not window:
            break
        paged.extend(window)
        offset += 2
    assert [r.id for r in paged] == [r.id for r in all_rows], "paging must not duplicate or skip"
    assert len(await port.list_for_user(user, limit=MAX_LIST_LIMIT + 50)) == 5, "limit is clamped, not rejected"
    await port.delete_user(user)


async def check_search_contract(port) -> None:
    """§5.1、§5.2、§5.4：只返回本人记忆；kinds 生效；limit 上限；空查询为空。"""
    user = _user()
    await port.add(user, [
        _item("喜欢喝茶", kind=MemoryKind.PREFERENCE),
        _item("在准备面试", kind=MemoryKind.EVENT),
        _item("住在上海", kind=MemoryKind.FACT),
    ])
    assert await port.search(user, "   ", limit=5) == []
    events = await port.search(user, "面试", limit=5, kinds=[MemoryKind.EVENT])
    assert [i.content for i in events] == ["在准备面试"]
    assert await port.search(user, "面试", limit=5, kinds=[MemoryKind.PREFERENCE]) == []
    many = await port.search(user, "在", limit=MAX_SEARCH_LIMIT + 100)
    assert len(many) <= MAX_SEARCH_LIMIT
    assert len(await port.search(user, "在", limit=1)) <= 1
    await port.delete_user(user)


async def check_delete_semantics(port) -> None:
    """§6：真删除；删除后既不列出也不召回；delete_user 返回条数且清空。"""
    user = _user()
    [keep, drop] = await port.add(user, [_item("要保留的茶"), _item("要删除的咖啡")])
    assert await port.delete_one(user, drop.id) is True
    assert await port.delete_one(user, drop.id) is False, "second delete must report not found"
    assert [i.content for i in await port.search(user, "咖啡", limit=5)] == []
    assert [i.content for i in await port.list_for_user(user, limit=10)] == ["要保留的茶"]
    assert await port.delete_user(user) == 1
    assert await port.list_for_user(user, limit=10) == []
    assert await port.search(user, "茶", limit=5) == []
    assert await port.delete_user(user) == 0, "deleting an empty user returns zero"


async def check_port(port) -> None:
    """运行全部一致性检查。任一失败即抛出 AssertionError。"""
    await check_write_roundtrip(port)
    await check_validation(port)
    await check_atomic_and_no_overwrite(port)
    await check_isolation(port)
    await check_list_order_and_paging(port)
    await check_search_contract(port)
    await check_delete_semantics(port)
