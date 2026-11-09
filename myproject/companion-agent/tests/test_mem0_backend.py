"""mem0 后端对真实 Qdrant 的契约测试（需要 COMPANION_TEST_QDRANT_URL）。

注意：向量由**测试用的确定性嵌入器**生成（按字符哈希），只验证隔离、归属、删除与过滤，
不验证语义召回质量。语义质量需要真实的多语言嵌入模型，见 T9/T13 报告。
"""

import asyncio
import hashlib
import os
import uuid

import pytest

from companion.ports.memory import MemoryItem, MemoryKind

QDRANT = os.environ.get("COMPANION_TEST_QDRANT_URL", "")
pytestmark = pytest.mark.skipif(not QDRANT, reason="COMPANION_TEST_QDRANT_URL not set")
DIMS = 64


class HashEmbedder:
    """测试替身：同一文本得到同一向量，不同文本大概率不同。仅用于契约测试。"""

    def __init__(self):
        self.store = {}

    def embed(self, text: str) -> list[float]:
        # 用 sha256 逐块扩展到 DIMS 维（每块 32 字节 → 32 维），保证宽度与集合一致
        out: list[float] = []
        counter = 0
        while len(out) < DIMS:
            digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
            out.extend(b / 255.0 for b in digest)
            counter += 1
        return out[:DIMS]


def _backend(collection: str):
    from qdrant_client import QdrantClient
    from memory_hub.mem0_backend import Mem0Backend
    from mem0 import Memory

    emb = HashEmbedder()
    memory = Memory.from_config({
        "vector_store": {"provider": "qdrant", "config": {
            "collection_name": collection, "embedding_model_dims": DIMS, "url": QDRANT, "on_disk": False}},
        "embedder": {"provider": "openai", "config": {"model": "x", "embedding_dims": DIMS,
                                                       "openai_base_url": "http://127.0.0.1:9", "api_key": "x"}},
        "llm": {"provider": "openai", "config": {"model": "x", "openai_base_url": "http://127.0.0.1:9", "api_key": "x"}},
    })
    # 把测试嵌入器接到 mem0 的 embedder 上（只在测试进程内生效）
    memory.embedding_model.embed = lambda text, memory_action=None: emb.embed(text)
    return Mem0Backend(collection=collection, qdrant_url=QDRANT, qdrant_api_key=None,
                       embedding_model="test", embedding_dims=DIMS, memory=memory), memory


def _item(content: str) -> MemoryItem:
    return MemoryItem(id=uuid.uuid4().hex, content=content, kind=MemoryKind.FACT, source_character_id="linche")


def test_isolation_delete_and_ownership_over_real_qdrant():
    collection = "ca_test_" + uuid.uuid4().hex[:8]
    backend, memory = _backend(collection)
    alice, bob = "companion:alice", "companion:bob"
    a1, a2 = _item("喜欢喝茶"), _item("在准备面试")
    try:
        asyncio.run(backend.add(alice, [a1, a2]))
        asyncio.run(backend.add(bob, [_item("喜欢咖啡")]))

        alice_rows = asyncio.run(backend.list_for_user(alice, limit=10))
        assert {r.content for r in alice_rows} == {"喜欢喝茶", "在准备面试"}
        # 跨用户：bob 看不到 alice 的任何记忆
        bob_rows = asyncio.run(backend.list_for_user(bob, limit=10))
        assert {r.content for r in bob_rows} == {"喜欢咖啡"}

        # 归属：bob 不能删 alice 的记忆；本人可以删
        assert asyncio.run(backend.delete_one(bob, a1.id)) is False
        assert asyncio.run(backend.delete_one(alice, a1.id)) is True
        remaining = asyncio.run(backend.list_for_user(alice, limit=10))
        assert {r.content for r in remaining} == {"在准备面试"}

        # 整用户删除（注销）
        assert asyncio.run(backend.delete_user(alice)) == 1
        assert asyncio.run(backend.list_for_user(alice, limit=10)) == []
        assert {r.content for r in asyncio.run(backend.list_for_user(bob, limit=10))} == {"喜欢咖啡"}
    finally:
        memory.vector_store.client.delete_collection(collection)
