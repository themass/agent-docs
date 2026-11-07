"""测试用内存记忆后端。

不是 mock 框架的替身，而是确定性实现：检索用词重合打分、按时间倒序、按用户隔离，
这样上层的召回注入、来源标注、删除零残留都可以在无网络下断言。
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Sequence
from dataclasses import replace

from companion.memory.extraction import search_terms
from companion.memory.port import MemoryItem, utc_now


class InMemoryMemoryPort:
    def __init__(self) -> None:
        self._items: dict[str, list[MemoryItem]] = {}
        self.calls: list[tuple[str, str]] = []

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        self.calls.append(("add", user_id))
        bucket = self._items.setdefault(user_id, [])
        stored: list[MemoryItem] = []
        for item in items:
            entry = replace(
                copy.deepcopy(item),
                id=item.id or f"mem-{uuid.uuid4().hex}",
                created_at=item.created_at or utc_now(),
                score=None,
            )
            bucket.append(entry)
            stored.append(copy.deepcopy(entry))
        return stored

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryItem]:
        self.calls.append(("search", user_id))
        terms = search_terms(query)
        scored: list[MemoryItem] = []
        for item in self._items.get(user_id, []):
            overlap = sum(1 for term in terms if term in item.content.casefold())
            if overlap:
                scored.append(replace(copy.deepcopy(item), score=float(overlap)))
        scored.sort(key=lambda i: (i.score or 0.0, i.created_at), reverse=True)
        return scored[: max(0, limit)]

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        self.calls.append(("delete_one", user_id))
        bucket = self._items.get(user_id, [])
        for index, item in enumerate(bucket):
            if item.id == memory_id:
                bucket.pop(index)
                return True
        return False

    async def delete_user(self, user_id: str) -> int:
        self.calls.append(("delete_user", user_id))
        return len(self._items.pop(user_id, []))

    async def list_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[MemoryItem]:
        self.calls.append(("list_for_user", user_id))
        ordered = sorted(
            self._items.get(user_id, []), key=lambda i: i.created_at, reverse=True
        )
        window = ordered[offset : offset + max(0, limit)]
        return [copy.deepcopy(item) for item in window]

    # 仅测试用：断言零残留时直接看原始存储，不经过任何检索路径。
    def raw_count(self, user_id: str) -> int:
        return len(self._items.get(user_id, []))
