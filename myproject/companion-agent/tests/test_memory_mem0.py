"""mem0 适配层测试。

不需要装 mem0ai：适配层接受注入的客户端，这里用一个按 mem0 ``Memory`` 方法形状
实现的内存客户端（add/search/get_all/get/delete/delete_all）来断言映射与删除语义。
"""

from __future__ import annotations

import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from companion.adapters.memory.mem0 import META_CHARACTER, META_CREATED_AT, META_KIND, META_MESSAGE, Mem0MemoryPort, Mem0Unavailable, available
from companion.ports.memory import MemoryItem, MemoryKind


class FakeMem0Client:
    """按 mem0 ``Memory`` 的形状存条目；检索用词重合打分，不做真向量。"""

    def __init__(self, *, delete_all_is_soft: bool = False, leaky_search: bool = False):
        self.rows: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []
        self.thread_ids: set[int] = set()
        # 模拟「delete_all 只删索引、不删原始记录」的版本差异。
        self.delete_all_is_soft = delete_all_is_soft
        # 模拟云端 filters 配错：search 无视 user_id 返回别人的条目。
        self.leaky_search = leaky_search

    # -- mem0 方法形状 ---------------------------------------------------
    def add(self, messages, *, user_id, metadata=None, infer=False):
        self.thread_ids.add(threading.get_ident())
        self.calls.append(("add", {"user_id": user_id, "metadata": dict(metadata or {})}))
        content = messages[-1]["content"] if messages else ""
        memory_id = f"m-{uuid.uuid4().hex[:8]}"
        row = {
            "id": memory_id,
            "memory": content,
            "user_id": user_id,
            "metadata": dict(metadata or {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.rows[memory_id] = row
        return {"results": [dict(row)]}

    def search(self, query, *, user_id, limit=5, **kwargs):
        self.thread_ids.add(threading.get_ident())
        self.calls.append(("search", {"user_id": user_id, "query": query}))
        terms = [t for t in query.casefold().split() if t]
        hits = []
        for row in self.rows.values():
            if not self.leaky_search and row["user_id"] != user_id:
                continue
            overlap = sum(1 for t in terms if t in row["memory"].casefold())
            if overlap or not terms:
                hits.append({**row, "score": float(overlap)})
        hits.sort(key=lambda r: r["score"], reverse=True)
        return hits[:limit]

    def get_all(self, *, user_id, limit=100, offset=0, **kwargs):
        self.thread_ids.add(threading.get_ident())
        self.calls.append(("get_all", {"user_id": user_id, "limit": limit, "offset": offset}))
        mine = [r for r in self.rows.values() if r["user_id"] == user_id]
        mine.sort(key=lambda r: r["created_at"], reverse=True)
        return {"results": [dict(r) for r in mine[offset : offset + limit]]}

    def get(self, memory_id):
        row = self.rows.get(memory_id)
        return dict(row) if row else None

    def delete(self, memory_id):
        self.calls.append(("delete", {"memory_id": memory_id}))
        self.rows.pop(memory_id, None)

    def delete_all(self, *, user_id):
        self.calls.append(("delete_all", {"user_id": user_id}))
        if self.delete_all_is_soft:
            return {"message": "deleted"}
        removed = [k for k, r in self.rows.items() if r["user_id"] == user_id]
        for key in removed:
            self.rows.pop(key, None)
        return {"deleted": len(removed)}

    # -- 测试辅助 --------------------------------------------------------
    def count(self, user_id: str) -> int:
        return sum(1 for r in self.rows.values() if r["user_id"] == user_id)

    def owners(self) -> set[str]:
        return {r["user_id"] for r in self.rows.values()}


def item(content, *, kind=MemoryKind.FACT, character="linche", message="msg-1", when=None):
    return MemoryItem(
        id="",
        content=content,
        kind=kind,
        source_character_id=character,
        source_message_id=message,
        created_at=when or datetime.now(timezone.utc),
    )


# -- 写入与来源往返 ------------------------------------------------------


async def test_add_returns_backend_ids_and_roundtrips_provenance():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)

    stored = await port.add(
        "u1", [item("用户养了一只叫团子的猫", character="linche", message="msg-42")]
    )

    assert len(stored) == 1
    assert stored[0].id.startswith("m-")
    assert stored[0].id in client.rows

    # metadata 按字符串写进后端，两个审计字段必须都在
    meta = client.rows[stored[0].id]["metadata"]
    assert meta[META_CHARACTER] == "linche"
    assert meta[META_MESSAGE] == "msg-42"
    assert meta[META_KIND] == MemoryKind.FACT.value
    assert META_CREATED_AT in meta

    reloaded = await port.list_for_user("u1")
    assert reloaded[0].source_character_id == "linche"
    assert reloaded[0].source_message_id == "msg-42"
    assert reloaded[0].content == "用户养了一只叫团子的猫"


async def test_roundtrip_preserves_kind_and_created_at():
    when = datetime(2026, 3, 4, 5, 6, tzinfo=timezone.utc)
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)

    await port.add("u1", [item("用户偏爱安静", kind=MemoryKind.PREFERENCE, when=when)])
    (back,) = await port.list_for_user("u1")

    assert back.kind is MemoryKind.PREFERENCE
    assert back.created_at == when
    assert back.score is None


async def test_search_result_keeps_provenance_and_score():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    await port.add("u1", [item("用户讨厌香菜", character="sudai", message="msg-9")])

    (hit,) = await port.search("u1", "香菜")
    assert hit.source_character_id == "sudai"
    assert hit.source_message_id == "msg-9"
    assert hit.score == 1.0


async def test_add_batches_every_item():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)

    stored = await port.add("u1", [item("a", message="m1"), item("b", message="m2")])
    assert [s.content for s in stored] == ["a", "b"]
    assert {s.source_message_id for s in stored} == {"m1", "m2"}
    assert client.count("u1") == 2


async def test_sync_client_runs_off_the_event_loop_thread():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)

    await port.add("u1", [item("线程检查")])
    await port.search("u1", "线程")
    await port.list_for_user("u1")

    assert client.thread_ids, "客户端没有被调用"
    # 同步客户端必须经 asyncio.to_thread；同线程调用说明会卡住事件循环。
    assert threading.get_ident() not in client.thread_ids


class AsyncFakeMem0Client(FakeMem0Client):
    """mem0 的异步版客户端：同名方法返回协程，适配层要直接 await 而不是丢线程。"""

    async def add(self, messages, *, user_id, metadata=None, infer=False):
        return super().add(messages, user_id=user_id, metadata=metadata, infer=infer)

    async def search(self, query, *, user_id, limit=5, **kwargs):
        return super().search(query, user_id=user_id, limit=limit, **kwargs)

    async def get_all(self, *, user_id, limit=100, offset=0, **kwargs):
        return super().get_all(user_id=user_id, limit=limit, offset=offset, **kwargs)

    async def delete(self, memory_id):
        return super().delete(memory_id)

    async def delete_all(self, *, user_id):
        return super().delete_all(user_id=user_id)


async def test_async_client_is_awaited_directly():
    client = AsyncFakeMem0Client()
    port = Mem0MemoryPort(client)

    (stored,) = await port.add("u1", [item("异步客户端", message="m-async")])
    assert stored.source_message_id == "m-async"
    (hit,) = await port.search("u1", "异步")
    assert hit.content == "异步客户端"

    await port.delete_user("u1")
    assert client.count("u1") == 0


# -- 用户隔离 ------------------------------------------------------------


async def test_search_is_scoped_to_the_requested_user():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    await port.add("u1", [item("u1 的秘密", message="m-u1")])
    await port.add("u2", [item("u2 的秘密", message="m-u2")])

    (hit,) = await port.search("u2", "秘密")
    assert hit.content == "u2 的秘密"
    assert hit.source_message_id == "m-u2"

    # 每次调用都必须带上 user_id，隔离靠它
    for name, kwargs in client.calls:
        if name in {"add", "search", "get_all", "delete_all"}:
            assert kwargs["user_id"] in {"u1", "u2"}


async def test_search_drops_rows_the_backend_leaked_from_other_users():
    # 云端 filters 配错时 mem0 会返回别人的条目；适配层要再拦一道。
    client = FakeMem0Client(leaky_search=True)
    port = Mem0MemoryPort(client)
    await port.add("u1", [item("u1 的条目")])
    await port.add("u2", [item("u2 的条目")])

    hits = await port.search("u2", "条目")
    assert {h.content for h in hits} == {"u2 的条目"}


async def test_list_for_user_never_returns_other_users_rows():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    await port.add("u1", [item("u1 的")])
    await port.add("u2", [item("u2 的")])

    assert [i.content for i in await port.list_for_user("u2")] == ["u2 的"]


async def test_empty_user_id_is_rejected():
    port = Mem0MemoryPort(FakeMem0Client())
    with pytest.raises(ValueError):
        await port.add("", [item("x")])
    # 空 user_id 在 mem0 里等于「不筛用户」，delete_user 会误删全站数据。
    with pytest.raises(ValueError):
        await port.delete_user("  ")


# -- 单条删除 ------------------------------------------------------------


async def test_delete_one_removes_only_that_row():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    stored = await port.add("u1", [item("第一条"), item("第二条")])

    assert await port.delete_one("u1", stored[0].id) is True
    assert [i.content for i in await port.list_for_user("u1")] == ["第二条"]

    assert await port.delete_one("u1", stored[0].id) is False
    assert await port.delete_one("u1", "") is False


async def test_delete_one_checks_ownership_before_deleting():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    (theirs,) = await port.add("u2", [item("u2 的条目")])

    assert await port.delete_one("u1", theirs.id) is False
    assert client.count("u2") == 1


# -- 账号删除 ------------------------------------------------------------


async def test_delete_user_removes_everything_and_spares_other_users():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    await port.add("u1", [item("a"), item("b"), item("c")])
    await port.add("u2", [item("d")])

    assert await port.delete_user("u1") == 3
    assert await port.list_for_user("u1") == []
    assert await port.search("u1", "a") == []
    assert await port.purge_ok("u1") is True
    assert client.count("u1") == 0
    assert client.count("u2") == 1


async def test_delete_user_is_complete_even_when_delete_all_is_soft():
    # 有的 mem0 版本 delete_all 只删索引、留下原始记录；账号删除不能信它。
    client = FakeMem0Client(delete_all_is_soft=True)
    port = Mem0MemoryPort(client)
    await port.add("u1", [item(f"第{i}条") for i in range(3)])

    await port.delete_user("u1")

    assert client.count("u1") == 0
    assert await port.purge_ok("u1") is True


async def test_delete_user_drains_more_than_one_page():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    await port.add("u1", [item(f"第{i}条") for i in range(450)])
    assert client.count("u1") == 450

    assert await port.delete_user("u1") == 450
    assert client.count("u1") == 0


async def test_delete_user_on_empty_user_is_zero():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    assert await port.delete_user("nobody") == 0
    assert await port.purge_ok("nobody") is True


async def test_delete_user_reports_none_when_counting_fails():
    class BrokenGetAll(FakeMem0Client):
        def get_all(self, *, user_id, limit=100, offset=0, **kwargs):
            raise RuntimeError("vector store down")

    client = BrokenGetAll()
    port = Mem0MemoryPort(client)
    # 数不出来不代表不能删：不抛异常，条数未知返回 None。
    assert await port.delete_user("u1") is None


# -- 列表分页 ------------------------------------------------------------


async def test_list_paginates_newest_first():
    client = FakeMem0Client()
    port = Mem0MemoryPort(client)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await port.add(
        "u1",
        [item(f"第{i}条", when=base + timedelta(minutes=i)) for i in range(5)],
    )

    all_items = await port.list_for_user("u1")
    assert [i.content for i in all_items] == ["第4条", "第3条", "第2条", "第1条", "第0条"]

    page = await port.list_for_user("u1", limit=2, offset=1)
    assert [i.content for i in page] == ["第3条", "第2条"]


# -- 依赖缺失 ------------------------------------------------------------


def test_unavailable_when_mem0ai_is_missing(monkeypatch):
    # 置 None 让 `import mem0` 抛 ImportError，模拟没装 mem0ai 的环境。
    monkeypatch.setitem(sys.modules, "mem0", None)
    with pytest.raises(Mem0Unavailable):
        Mem0MemoryPort()


def test_module_imports_and_reports_availability_without_mem0(monkeypatch):
    monkeypatch.setitem(sys.modules, "mem0", None)
    assert available() is False
    # 本模块本身能 import（不拉起后端），注入客户端也不需要 mem0ai。
    port = Mem0MemoryPort(FakeMem0Client())
    assert port is not None


def test_injected_client_never_touches_mem0ai(monkeypatch):
    monkeypatch.setitem(sys.modules, "mem0", None)
    # 明确传 client 时连探测都不该发生：离线链路与测试走这条路。
    Mem0MemoryPort(FakeMem0Client(), infer=False)
