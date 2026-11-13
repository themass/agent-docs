"""持久化记忆（MySQL）：写入后用新的实例读取，证明重启不丢（需要 COMPANION_TEST_MYSQL_URL）。"""

import asyncio
import os
import uuid

import pytest

from companion.domain.timeline.models import TimelineEvent  # noqa: F401 — 保证模块加载
from companion.memory.port import MemoryItem, MemoryKind

MYSQL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not MYSQL, reason="COMPANION_TEST_DATABASE_URL not set")


def _engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(MYSQL, pool_pre_ping=True)


def test_memory_survives_a_fresh_instance(memory_schema):
    from companion.memory.sql import SqlMemoryPort

    user = f"test-durable-{uuid.uuid4().hex[:8]}"
    item = MemoryItem(id=uuid.uuid4().hex, content="喜欢喝茶", kind=MemoryKind.FACT, source_character_id="linche")

    async def go():
        first = _engine()
        second = _engine()
        try:
            await SqlMemoryPort(first).add(user, [item])
            # 模拟重启：另一个引擎、另一个端口实例
            rows = await SqlMemoryPort(second).list_for_user(user, limit=10)
            assert [r.content for r in rows] == ["喜欢喝茶"]
            hits = await SqlMemoryPort(second).search(user, "茶", limit=5)
            assert [h.id for h in hits] == [item.id]
            assert await SqlMemoryPort(second).delete_one(user, item.id)
            assert await SqlMemoryPort(second).list_for_user(user, limit=10) == []
        finally:
            await first.dispose()
            await second.dispose()

    asyncio.run(go())


def test_durable_search_ranks_by_words_not_substring(memory_schema):
    from companion.memory.sql import SqlMemoryPort

    user = f"test-rank-{uuid.uuid4().hex[:8]}"
    items = [MemoryItem(id=uuid.uuid4().hex, content=c, kind=MemoryKind.FACT, source_character_id="linche")
             for c in ["喜欢喝茶", "在准备面试", "喜欢咖啡"]]

    async def go():
        engine = _engine()
        try:
            port = SqlMemoryPort(engine)
            await port.add(user, items)
            hits = await port.search(user, "咖啡", limit=5)
            assert [h.content for h in hits] == ["喜欢咖啡"]
            assert [h.content for h in await port.search(user, "火箭", limit=5)] == []
            await port.delete_user(user)
        finally:
            await engine.dispose()

    asyncio.run(go())
