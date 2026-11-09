"""持久化的记忆后端（MySQL，表 ca_memory_item）。

持久化的记忆（不依赖向量或模型）。检索是词法排序（domain/memory/recall.py），不是语义匹配。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, String, Table, Text, and_, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.adapters.store.mysql.schema import TABLE_PREFIX, metadata as schema_metadata
from companion.domain.memory.recall import rank
from companion.ports.memory import MemoryItem, MemoryKind

SEARCH_WINDOW = 500  # 每个用户参与排序的最近条数上限

memory_item = Table(
    TABLE_PREFIX + "memory_item", schema_metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("content", Text, nullable=False),
    Column("source_character_id", String(64), nullable=False, server_default=""),
    Column("source_message_id", String(64), nullable=False, server_default=""),
    Column("created_at", DateTime, nullable=False),
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


class MysqlMemoryPort:
    """MemoryPort 的 MySQL 实现。user_id 是复合 app:uid（由 memory_hub 加上）。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, user_id: str, items: Any) -> list[MemoryItem]:
        rows = [{
            "id": item.id, "user_id": user_id, "kind": item.kind.value, "content": item.content,
            "source_character_id": item.source_character_id or "", "source_message_id": item.source_message_id or "",
            "created_at": _now(),
        } for item in items]
        if rows:
            async with self._engine.begin() as conn:
                await conn.execute(insert(memory_item), rows)
        return list(items)

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryItem]:
        """在该用户最近的 SEARCH_WINDOW 条中做词法排序（不做全表扫描，也不依赖向量）。"""
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(memory_item).where(memory_item.c.user_id == user_id)
                                       .order_by(memory_item.c.created_at.desc()).limit(SEARCH_WINDOW))).mappings().all()
        candidates = [(_to_item(r), r["content"], r["created_at"]) for r in rows]
        return rank(query, candidates, limit)

    async def list_for_user(self, user_id: str, limit: int = 20, offset: int = 0) -> list[MemoryItem]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(memory_item).where(memory_item.c.user_id == user_id)
                                       .order_by(memory_item.c.created_at.desc())
                                       .limit(limit).offset(offset))).mappings().all()
        return [_to_item(r) for r in rows]

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(memory_item).where(and_(
                memory_item.c.id == memory_id, memory_item.c.user_id == user_id)))
        return res.rowcount == 1

    async def delete_user(self, user_id: str) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(memory_item).where(memory_item.c.user_id == user_id))
        return res.rowcount


def _to_item(row) -> MemoryItem:
    return MemoryItem(id=row["id"], content=row["content"], kind=MemoryKind(row["kind"]),
                      source_character_id=row["source_character_id"], source_message_id=row["source_message_id"],
                      created_at=row["created_at"].replace(tzinfo=UTC))
