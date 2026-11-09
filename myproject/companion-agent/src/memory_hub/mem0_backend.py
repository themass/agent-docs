"""mem0 后端（源码集成，见 vendor/README.md）。

把 mem0 的 Memory 适配成我们的 MemoryPort 形状。约定：
- user_id 是 memory_hub 给的复合 app:uid，原样交给 mem0 作为过滤字段（D §10.1）；
- 每个应用一个 collection（D §10.2），在构造时决定，不由调用方传入；
- 不做 mem0 的隐式抽取（infer=False）：记忆内容由我们的抽取层给出，mem0 只负责向量化与存取；
- 遥测默认关闭（MEM0_TELEMETRY=False），用户数据不发往第三方。
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

# 必须在导入 mem0 之前设置：它在导入期读取该变量。
os.environ.setdefault("MEM0_TELEMETRY", "False")

from companion.ports.memory import MemoryItem, MemoryKind  # noqa: E402  (依赖方向：memory_hub 只依赖 companion.ports)


class Mem0Backend:
    def __init__(self, *, collection: str, qdrant_url: str, qdrant_api_key: str | None,
                 embedding_model: str, embedding_dims: int, memory: Any = None) -> None:
        """memory 可注入（测试用）；为空时按配置构造真实的 mem0 Memory。"""
        if memory is None:
            from mem0 import Memory

            memory = Memory.from_config({
                "vector_store": {"provider": "qdrant", "config": {
                    "collection_name": collection, "embedding_model_dims": embedding_dims,
                    "url": qdrant_url, "api_key": qdrant_api_key, "on_disk": True}},
                "embedder": {"provider": "fastembed", "config": {
                    "model": embedding_model, "embedding_dims": embedding_dims}},
                "llm": {"provider": "openai", "config": {"model": "unused-without-infer"}},
            })
        self._memory = memory
        self._collection = collection

    async def add(self, user_id: str, items: Sequence[MemoryItem]) -> list[MemoryItem]:
        out = []
        for item in items:
            meta = {"kind": item.kind.value, "source_character_id": item.source_character_id,
                    "source_message_id": item.source_message_id, "app_item_id": item.id}
            self._memory.add(item.content, user_id=user_id, metadata=meta, infer=False)
            out.append(item)
        return out

    async def search(self, user_id: str, query: str, limit: int = 5) -> list[MemoryItem]:
        res = self._memory.search(query, filters={"user_id": user_id}, top_k=limit)
        return [_to_item(r) for r in _results(res)]

    async def list_for_user(self, user_id: str, limit: int = 20, offset: int = 0) -> list[MemoryItem]:
        res = self._memory.get_all(filters={"user_id": user_id}, top_k=limit + offset)
        return [_to_item(r) for r in _results(res)][offset:offset + limit]

    async def delete_one(self, user_id: str, memory_id: str) -> bool:
        """我们的 id 存在 metadata.app_item_id 里（mem0 自己的向量 id 是它生成的）。
        先按 user_id 过滤找到对应的 mem0 id，核对归属后再删（mem0 的 delete 不校验归属）。"""
        rows = _results(self._memory.get_all(filters={"user_id": user_id}, top_k=10_000))
        target = next((r for r in rows if str((r.get("metadata") or {}).get("app_item_id")) == memory_id), None)
        if target is None:
            return False
        self._memory.delete(memory_id=target["id"])
        return True

    async def delete_user(self, user_id: str) -> int:
        rows = _results(self._memory.get_all(filters={"user_id": user_id}, top_k=10_000))
        for row in rows:
            self._memory.delete(memory_id=row["id"])
        return len(rows)


def _results(res: Any) -> list[dict[str, Any]]:
    if isinstance(res, dict):
        return list(res.get("results", []))
    return list(res or [])


def _to_item(row: dict[str, Any]) -> MemoryItem:
    meta = row.get("metadata") or {}
    kind = meta.get("kind", MemoryKind.FACT.value)
    return MemoryItem(
        id=str(meta.get("app_item_id") or row.get("id")),
        content=row.get("memory", ""),
        kind=MemoryKind(kind) if kind in MemoryKind._value2member_map_ else MemoryKind.FACT,
        source_character_id=meta.get("source_character_id", ""),
        source_message_id=meta.get("source_message_id", ""),
        score=row.get("score"),
    )
