"""角色卡的存储层（P6）：card + version 两张表之上的服务语义。

- 一个 (owner, role) 一张卡；卡上的 ``active_version`` 是提示词读的那一个版本号。
- 生效字段 = base + 版本号 ≤ active 的变更集按 version 升序叠加（model.merge_chain）。
- 回退/切换只是移动 active_version，历史版本保留（可观、可再切回去）。

fake 实现先钉语义（进程内、按同一断言跑）；SQL 实现在 sql.py，两者对同一套语义。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from companion.service.card.model import merge_chain, normalize_changeset


class CardNotFound(KeyError):
    """卡不存在、不属于该 owner、或指定版本号不存在——对调用方不可区分（同记忆接口的口径）。"""


@dataclass(frozen=True, slots=True)
class CardVersionRecord:
    version: int
    changes: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CardRecord:
    owner_id: int
    role_id: str
    base: dict[str, Any]
    active_version: int
    versions: list[CardVersionRecord] = field(default_factory=list)

    @property
    def version_count(self) -> int:
        return len(self.versions)


@dataclass(frozen=True, slots=True)
class EffectiveCard:
    """提示词组装要的那份：当前生效版本号 + 合并后的字段。"""

    role_id: str
    version: int
    fields: dict[str, Any]
    truncated: bool = False


class CardStore(Protocol):
    async def get(self, *, owner_id: int, role_id: str) -> CardRecord | None: ...

    async def create(self, *, owner_id: int, role_id: str, base: dict[str, Any],
                     changes: dict[str, Any]) -> CardRecord: ...

    async def add_version(self, *, owner_id: int, role_id: str, changes: dict[str, Any],
                          make_active: bool) -> CardRecord: ...

    async def set_active(self, *, owner_id: int, role_id: str, version: int) -> CardRecord: ...


class InMemoryCardStore:
    """进程内实现（测试与无库装配用）。隔离边界是 (owner_id, role_id)，与记忆一致。"""

    def __init__(self) -> None:
        self._cards: dict[tuple[int, str], CardRecord] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, owner_id: int, role_id: str) -> CardRecord | None:
        return self._cards.get((owner_id, role_id))

    async def create(self, *, owner_id: int, role_id: str, base: dict[str, Any],
                     changes: dict[str, Any]) -> CardRecord:
        async with self._lock:
            if (owner_id, role_id) in self._cards:
                raise CardNotFound("card already exists")
            now = datetime.now(UTC)
            card = CardRecord(owner_id, role_id, dict(base), 1,
                              [CardVersionRecord(1, changes, now)])
            self._cards[(owner_id, role_id)] = card
            return card

    async def add_version(self, *, owner_id: int, role_id: str, changes: dict[str, Any],
                          make_active: bool) -> CardRecord:
        """追加一个版本；卡不存在时以空 base 建卡（第一次 append 就是 v1）。"""
        async with self._lock:
            card = self._cards.get((owner_id, role_id))
            if card is None:
                card = CardRecord(owner_id, role_id, {}, 0, [])
            version = (card.versions[-1].version if card.versions else 0) + 1
            updated = CardRecord(card.owner_id, card.role_id, card.base,
                                 version if make_active else card.active_version,
                                 [*card.versions, CardVersionRecord(version, changes, datetime.now(UTC))])
            self._cards[(owner_id, role_id)] = updated
            return updated

    async def set_active(self, *, owner_id: int, role_id: str, version: int) -> CardRecord:
        async with self._lock:
            card = self._cards.get((owner_id, role_id))
            if card is None or not any(v.version == version for v in card.versions):
                raise CardNotFound("no such card version")
            updated = CardRecord(card.owner_id, card.role_id, card.base, version, card.versions)
            self._cards[(owner_id, role_id)] = updated
            return updated


class CardService:
    """版本解析与合并的入口。API 层只和它打交道。"""

    def __init__(self, store: CardStore) -> None:
        self._store = store

    async def create(self, *, owner_id: int, role_id: str, base: dict[str, Any],
                     first_changes: dict[str, Any] | None = None) -> CardRecord:
        changes = normalize_changeset(first_changes) if first_changes else {}
        return await self._store.create(owner_id=owner_id, role_id=role_id,
                                        base=dict(base), changes=changes)

    async def append_version(self, *, owner_id: int, role_id: str,
                             changes: dict[str, Any]) -> CardVersionRecord:
        normalized = normalize_changeset(changes)
        card = await self._store.add_version(owner_id=owner_id, role_id=role_id,
                                             changes=normalized, make_active=True)
        return card.versions[-1]

    async def set_active(self, *, owner_id: int, role_id: str, version: int) -> CardRecord:
        return await self._store.set_active(owner_id=owner_id, role_id=role_id, version=version)

    rollback = set_active  # 回退 = 把 active 挪回旧版本；历史不删

    async def list_versions(self, *, owner_id: int, role_id: str) -> list[CardVersionRecord]:
        card = await self._store.get(owner_id=owner_id, role_id=role_id)
        if card is None:
            return []
        return list(card.versions)

    async def effective(self, *, owner_id: int, role_id: str) -> EffectiveCard | None:
        """提示词注入点要的那份：base + 版本号 ≤ active 的链，按 version 升序叠加。"""
        card = await self._store.get(owner_id=owner_id, role_id=role_id)
        if card is None:
            return None
        chain = [v.changes for v in sorted(card.versions, key=lambda v: v.version)
                 if v.version <= card.active_version]
        return EffectiveCard(role_id=role_id, version=card.active_version,
                             fields=merge_chain(card.base, chain))
