"""持久化的记忆后端（MySQL，表 ca_memory_item）。

持久化的记忆（不依赖向量或模型）。检索是词法排序（domain/memory/recall.py），不是语义匹配。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String, Table, Text, and_, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import TABLE_PREFIX, metadata as schema_metadata
from companion.agent.memory.recall import rank_scored
from companion.agent.memory.port import (
    MAX_BATCH,
    MAX_LIST_LIMIT,
    MAX_SEARCH_LIMIT,
    MemoryInvalid,
    MemoryItem,
    MemoryKind,
    validate_content,
    validate_user_id,
)

SEARCH_WINDOW = 500  # 每个用户参与排序的最近条数上限（规范 §5.3）

memory_item = Table(
    TABLE_PREFIX + "memory_item", schema_metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("content", Text, nullable=False),
    Column("source_character_id", String(64), nullable=False, server_default=""),
    Column("source_message_id", String(64), nullable=False, server_default=""),
    Column("created_at", DateTime, nullable=False),
    # 事实可以被「取代」而不是删除：新的那条 is_latest=1 并记下 supersedes_id，旧的回溯保留但不再被召回。
    # 用户说「我说错了」时能说清楚是哪条取代了哪条；删除仍然走 delete_one / delete_user。
    Column("supersedes_id", String(64), nullable=True),
    Column("is_latest", Boolean, nullable=False, server_default="1"),
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


class SqlMemoryPort:
    """MemoryPort 的 MySQL 实现。user_id 是复合 app:uid（由 memory_hub 加上）。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._auto_engine = None

    @property
    def _auto(self):
        """单语句读/写用的 autocommit 视图，首次使用时才建（理由见 db/sql.py 的同名属性）。

        这一处是上一轮「读路径也走 autocommit」漏掉的：契约测试保护的是 db/sql.py 里的
        那 7 个 store，召回走的是这里的 SqlMemoryPort 与 timeline/sql.py。实测同一句
        SELECT 默认连接 550 ms、autocommit 184 ms——召回超时 800 ms 的配置下，
        默认连接每回合必然超时，她一直拿不到任何记忆。
        """
        if self._auto_engine is None:
            self._auto_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        return self._auto_engine

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        validate_user_id(user_id)
        if len(items) > MAX_BATCH:
            raise MemoryInvalid(f"at most {MAX_BATCH} items per add")
        for item in items:
            validate_content(item.content)
        now = _now()
        rows = [{
            "id": item.id or uuid.uuid4().hex, "user_id": user_id, "kind": MemoryKind(item.kind).value,
            "content": item.content, "source_character_id": item.source_character_id or "",
            "source_message_id": item.source_message_id or "", "created_at": item.created_at.replace(tzinfo=None)
            if item.created_at else now,
        } for item in items]
        if rows:
            # 一次 INSERT（单语句在 InnoDB 中是原子的），失败则整批不写入
            try:
                async with self._engine.begin() as conn:
                    await conn.execute(insert(memory_item), rows)
            except IntegrityError as exc:
                raise MemoryInvalid("duplicate memory id") from exc  # 规范 §7.3：主键冲突即拒绝整批
        return [_to_item(r) for r in rows]

    async def search(self, user_id: str, query: str, limit: int = 5,
                     kinds: Iterable[MemoryKind] | None = None) -> list[MemoryItem]:
        """在该用户最近的 SEARCH_WINDOW 条中按 kinds 过滤后做词法排序（规范 §5）。"""
        validate_user_id(user_id)
        limit = max(0, min(limit, MAX_SEARCH_LIMIT))
        cond = [memory_item.c.user_id == user_id, memory_item.c.is_latest == True]  # noqa: E712 —— 被取代的不再召回
        if kinds:
            cond.append(memory_item.c.kind.in_([MemoryKind(k).value for k in kinds]))
        async with self._auto.connect() as conn:
            rows = (await conn.execute(select(memory_item).where(and_(*cond))
                                       .order_by(memory_item.c.created_at.desc(), memory_item.c.id.desc())
                                       .limit(SEARCH_WINDOW))).mappings().all()
        candidates = [(_to_item(r), r["content"], r["created_at"]) for r in rows]
        return [replace(r.item, score=r.score) for r in rank_scored(query, candidates, limit)]

    async def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0,
                            include_history: bool = False) -> list[MemoryItem]:
        """默认只列当前有效的事实；``include_history`` 时连被取代的一起（「为什么改了」）。"""
        validate_user_id(user_id)
        limit = max(0, min(limit, MAX_LIST_LIMIT))
        cond = [memory_item.c.user_id == user_id]
        if not include_history:
            cond.append(memory_item.c.is_latest == True)  # noqa: E712
        async with self._auto.connect() as conn:
            rows = (await conn.execute(select(memory_item).where(and_(*cond))
                                       .order_by(memory_item.c.created_at.desc(), memory_item.c.id.desc())
                                       .limit(limit).offset(max(0, offset)))).mappings().all()
        return [_to_item(r) for r in rows]

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        validate_user_id(user_id)
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(memory_item).where(and_(
                memory_item.c.id == memory_id, memory_item.c.user_id == user_id)))
        return res.rowcount == 1

    async def delete_user(self, user_id: str) -> int:
        validate_user_id(user_id)
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(memory_item).where(memory_item.c.user_id == user_id))
        return res.rowcount


    async def supersede(self, user_id: str, old_id: str, item: MemoryItem) -> MemoryItem | None:
        validate_user_id(user_id)
        validate_content(item.content)
        now = _now()
        new_id = item.id or uuid.uuid4().hex
        async with self._engine.begin() as conn:
            old = (await conn.execute(select(memory_item.c.id).where(and_(
                memory_item.c.id == old_id, memory_item.c.user_id == user_id)))).first()
            if old is None:
                return None
            await conn.execute(insert(memory_item).values(
                id=new_id, user_id=user_id, kind=MemoryKind(item.kind).value, content=item.content,
                source_character_id=item.source_character_id or "",
                source_message_id=item.source_message_id or "", created_at=now,
                supersedes_id=old_id, is_latest=True))
            await conn.execute(update(memory_item).where(and_(
                memory_item.c.id == old_id, memory_item.c.user_id == user_id)).values(is_latest=False))
        return replace(item, id=new_id, created_at=now.replace(tzinfo=UTC), is_latest=True, supersedes_id=old_id)


def _to_item(row) -> MemoryItem:
    return MemoryItem(id=row["id"], content=row["content"], kind=MemoryKind(row["kind"]),
                      source_character_id=row["source_character_id"], source_message_id=row["source_message_id"],
                      created_at=row["created_at"].replace(tzinfo=UTC),
                      is_latest=bool(row["is_latest"]) if "is_latest" in row.keys() else True,
                      supersedes_id=row["supersedes_id"] if "supersedes_id" in row.keys() else None)
