"""内存记忆后端：规范 v1 的参考实现，用于测试与离线运行。

与 MySQL 后端共用同一套召回排序（domain/memory/recall.py），两者对同样的数据给出同样的结果。
进程内存储，重启即丢。
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import replace

from companion.agent.memory.recall import rank_scored
from companion.agent.memory.port import (
    MAX_BATCH,
    MAX_LIST_LIMIT,
    MAX_SEARCH_LIMIT,
    MemoryInvalid,
    MemoryItem,
    MemoryKind,
    utc_now,
    validate_content,
    validate_user_id,
)


class InMemoryMemoryPort:
    def __init__(self) -> None:
        self._items: dict[str, list[MemoryItem]] = {}
        self.calls: list[tuple[str, str]] = []

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        self.calls.append(("add", user_id))
        validate_user_id(user_id)
        if len(items) > MAX_BATCH:
            raise MemoryInvalid(f"at most {MAX_BATCH} items per add")
        for item in items:
            validate_content(item.content)
        existing = {i.id for i in self._items.get(user_id, [])}
        supplied = [item.id for item in items if item.id]
        if len(set(supplied)) != len(supplied) or existing.intersection(supplied):
            raise MemoryInvalid("duplicate memory id")  # 规范 §7.3：不覆盖已有条目
        # 原子：先全部构造好，再一次性写入
        prepared = [
            replace(copy.deepcopy(item), id=item.id or f"mem-{uuid.uuid4().hex}",
                    created_at=item.created_at or utc_now(), score=None)
            for item in items
        ]
        self._items.setdefault(user_id, []).extend(prepared)
        return [copy.deepcopy(p) for p in prepared]

    async def search(self, user_id: str, query: str, limit: int = 5,
                     kinds: Iterable[MemoryKind] | None = None) -> list[MemoryItem]:
        self.calls.append(("search", user_id))
        validate_user_id(user_id)
        limit = max(0, min(limit, MAX_SEARCH_LIMIT))
        wanted = {MemoryKind(k) for k in kinds} if kinds else None
        pool = [i for i in self._items.get(user_id, []) if wanted is None or i.kind in wanted]
        ranked = rank_scored(query, [(i, i.content, i.created_at) for i in pool], limit)
        return [replace(copy.deepcopy(r.item), score=r.score) for r in ranked]

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        self.calls.append(("delete_one", user_id))
        validate_user_id(user_id)
        bucket = self._items.get(user_id, [])
        for index, item in enumerate(bucket):
            if item.id == memory_id:
                bucket.pop(index)
                return True
        return False

    async def delete_user(self, user_id: str) -> int:
        self.calls.append(("delete_user", user_id))
        validate_user_id(user_id)
        return len(self._items.pop(user_id, []))

    async def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0,
                            include_history: bool = False) -> list[MemoryItem]:
        self.calls.append(("list_for_user", user_id))
        validate_user_id(user_id)
        limit = max(0, min(limit, MAX_LIST_LIMIT))
        items = self._items.get(user_id, [])
        if not include_history:
            items = [i for i in items if i.is_latest]   # 与 SQL 后端一致：被取代的不列
        # 与 MySQL 后端一致：created_at 倒序，同一时间按 id 倒序（稳定分页，规范 §4）
        ordered = sorted(items, key=lambda i: (i.created_at, i.id), reverse=True)
        return [copy.deepcopy(i) for i in ordered[max(0, offset): max(0, offset) + limit]]

    async def supersede(self, user_id: str, old_id: str, item: MemoryItem) -> MemoryItem | None:
        self.calls.append(("supersede", user_id))
        validate_user_id(user_id)
        validate_content(item.content)
        rows = self._items.get(user_id, [])
        old = next((i for i in rows if i.id == old_id), None)
        if old is None:
            return None
        # 旧条目标为被取代（保留在历史里），新条目追加一条并记下来源
        new_item = replace(item, supersedes_id=old_id, is_latest=True)
        self._items[user_id] = [replace(i, is_latest=False) if i.id == old_id else i for i in rows] + [
            copy.deepcopy(new_item)]
        return new_item

    # 仅测试用：断言零残留时直接看原始存储，不经过任何检索路径。
    def raw_count(self, user_id: str) -> int:
        return len(self._items.get(user_id, []))
