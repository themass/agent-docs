"""紧凑记忆索引接口（P6）：把「下一回合会被注入什么」原样读出来。

存储与增删改仍走既有 /v1/memory/facts；这里只加只读的 index——用户点开「她记住了什么」
看到的就是策略选完之后的那几条，和注入顺序一致（卡在前、记忆在后）。
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.agent.memory.port import MemoryItem, MemoryKind
from companion.agent.memory.subject import role_subject
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers.memory_index import build_router
from companion.service.card.store import CardService, InMemoryCardStore


class FakePort:
    """MemoryPort 的最小实现（同 test_memory_hub 的假端口口径）。"""

    def __init__(self) -> None:
        self.items: dict[str, list[MemoryItem]] = {}

    async def add(self, user_id, items):
        self.items.setdefault(user_id, []).extend(items)
        return list(items)

    async def list_for_user(self, user_id, limit=50, offset=0, include_history=False):
        rows = list(self.items.get(user_id, []))
        return rows[offset:offset + limit]

    async def search(self, user_id, query, limit=5, kinds=None):
        return []

    async def delete_one(self, user_id, memory_id):
        rows = self.items.get(user_id, [])
        keep = [i for i in rows if i.id != memory_id]
        self.items[user_id] = keep
        return len(keep) != len(rows)

    async def delete_user(self, user_id):
        n = len(self.items.get(user_id, []))
        self.items[user_id] = []
        return n

    async def supersede(self, user_id, old_id, item):
        return None


@pytest.fixture
def env():
    port = FakePort()
    cards = CardService(InMemoryCardStore())
    app = FastAPI()
    app.include_router(build_router(memory=port, cards=cards,
                                    current_user=build_current_user(AllowAllVerifier())))
    return TestClient(app), port, cards


def _h(user="7"):
    return {"Authorization": f"Bearer {user}"}


def test_empty_index_returns_no_lines(env):
    client, _, _ = env
    r = client.get("/v1/memory/index", headers=_h())
    assert r.status_code == 200
    assert r.json() == {"lines": [], "memory_entries": 0, "card_version": 0}


def test_index_lists_facts_newest_first(env):
    client, port, _ = env
    subject = role_subject("7", None)
    port.items.setdefault(subject, []).extend([
        MemoryItem(id=uuid.uuid4().hex, content="住在杭州", created_at=_t(300)),
        MemoryItem(id=uuid.uuid4().hex, content="喜欢手冲", kind=MemoryKind.PREFERENCE, created_at=_t(1)),
    ])
    r = client.get("/v1/memory/index", headers=_h())
    lines = r.json()["lines"]
    assert lines == ["- 喜欢手冲", "- 住在杭州"]  # 偏好优先
    assert r.json()["memory_entries"] == 2


async def test_index_carries_active_card_lines_first(env):
    client, port, cards = env
    await cards.append_version(owner_id=7, role_id="linche", changes={"name": "小澈", "boundaries": ["不谈钱"]})
    await port.add(role_subject("7", "linche"), [MemoryItem(id=uuid.uuid4().hex, content="养了只猫")])
    r = client.get("/v1/memory/index?role_id=linche", headers=_h())
    assert r.json()["lines"] == ["- 名字：小澈", "- 关系边界：不谈钱", "- 养了只猫"]


async def test_index_respects_max_entries(env):
    client, port, _ = env
    await port.add(role_subject("7", None), [
        MemoryItem(id=uuid.uuid4().hex, content=f"事实{i}", created_at=_t(i)) for i in range(5)])
    r = client.get("/v1/memory/index?max_entries=2", headers=_h())
    assert len(r.json()["lines"]) == 2


async def test_index_is_user_isolated(env):
    client, port, _ = env
    await port.add(role_subject("7", None), [MemoryItem(id=uuid.uuid4().hex, content="私有事实")])
    assert client.get("/v1/memory/index", headers=_h("8")).json()["lines"] == []


def _t(minutes_ago: int):
    from datetime import datetime, timedelta, UTC
    return datetime.now(UTC) - timedelta(minutes=minutes_ago)
