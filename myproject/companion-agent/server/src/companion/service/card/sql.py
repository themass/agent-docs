"""ca_role_card / ca_role_card_version 的 SQL 实现（P6）。

约定与 db/sql.py 其余 store 一致：所有查询带 owner_id；单语句读走 autocommit 视图；
写用 engine.begin()；「不存在」与「不是你的」都返回/抛同一个不可区分的结果。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import role_card, role_card_version
from companion.service.card.store import (
    CardNotFound,
    CardRecord,
    CardVersionRecord,
)


def _now() -> datetime:
    return datetime.now(UTC)


class SqlCardStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._auto_engine = None

    @property
    def _auto(self):
        """单语句读/写用的 autocommit 视图（理由同 db/sql.py 同名属性）。"""
        if self._auto_engine is None:
            self._auto_engine = self._engine.execution_options(isolation_level="AUTOCOMMIT")
        return self._auto_engine

    async def get(self, *, owner_id: int, role_id: str) -> CardRecord | None:
        async with self._auto.connect() as conn:
            row = (await conn.execute(select(role_card).where(and_(
                role_card.c.owner_id == owner_id, role_card.c.role_id == role_id)))).mappings().first()
            if row is None:
                return None
            versions = (await conn.execute(select(role_card_version).where(and_(
                role_card_version.c.owner_id == owner_id, role_card_version.c.role_id == role_id))
                .order_by(role_card_version.c.version))).mappings().all()
        return _card(row, versions)

    async def create(self, *, owner_id: int, role_id: str, base: dict[str, Any],
                     changes: dict[str, Any]) -> CardRecord:
        now = _now()
        try:
            async with self._engine.begin() as conn:
                await conn.execute(insert(role_card).values(
                    owner_id=owner_id, role_id=role_id, base=base, active_version=1,
                    created_at=now, updated_at=now))
                await conn.execute(insert(role_card_version).values(
                    owner_id=owner_id, role_id=role_id, version=1, changes=changes, created_at=now))
        except IntegrityError as exc:  # (owner, role) 已有卡：与 fake 同口径
            raise CardNotFound("card already exists") from exc
        return CardRecord(owner_id, role_id, dict(base), 1, [CardVersionRecord(1, changes, now)])

    async def add_version(self, *, owner_id: int, role_id: str, changes: dict[str, Any],
                          make_active: bool) -> CardRecord:
        """追加一个版本；卡不存在时以空 base 建卡（第一次 append 就是 v1）。"""
        now = _now()
        async with self._engine.begin() as conn:
            card = (await conn.execute(select(role_card).where(and_(
                role_card.c.owner_id == owner_id, role_card.c.role_id == role_id)))).mappings().first()
            if card is None:
                await conn.execute(insert(role_card).values(
                    owner_id=owner_id, role_id=role_id, base={}, active_version=0,
                    created_at=now, updated_at=now))
                base: dict[str, Any] = {}
            else:
                base = dict(card["base"] or {})
            top = (await conn.execute(select(role_card_version.c.version).where(and_(
                role_card_version.c.owner_id == owner_id, role_card_version.c.role_id == role_id))
                .order_by(role_card_version.c.version.desc()).limit(1))).scalar()
            version = (top or 0) + 1
            await conn.execute(insert(role_card_version).values(
                owner_id=owner_id, role_id=role_id, version=version, changes=changes, created_at=now))
            if make_active:
                await conn.execute(update(role_card).where(and_(
                    role_card.c.owner_id == owner_id, role_card.c.role_id == role_id))
                    .values(active_version=version, updated_at=now))
            active = version if make_active else (card["active_version"] if card else 0)
        return CardRecord(owner_id, role_id, base, active,
                          [CardVersionRecord(version, changes, now)])

    async def set_active(self, *, owner_id: int, role_id: str, version: int) -> CardRecord:
        async with self._engine.begin() as conn:
            exists = (await conn.execute(select(role_card_version.c.id).where(and_(
                role_card_version.c.owner_id == owner_id, role_card_version.c.role_id == role_id,
                role_card_version.c.version == version)))).first()
            if exists is None:
                raise CardNotFound("no such card version")
            await conn.execute(update(role_card).where(and_(
                role_card.c.owner_id == owner_id, role_card.c.role_id == role_id))
                .values(active_version=version, updated_at=_now()))
        card = await self.get(owner_id=owner_id, role_id=role_id)
        assert card is not None
        return replace(card, active_version=version)


def _card(row, version_rows) -> CardRecord:
    return CardRecord(
        owner_id=row["owner_id"], role_id=row["role_id"], base=dict(row["base"] or {}),
        active_version=row["active_version"],
        versions=[CardVersionRecord(v["version"], dict(v["changes"] or {}),
                                    v["created_at"].replace(tzinfo=UTC) if v["created_at"].tzinfo is None
                                    else v["created_at"])
                  for v in version_rows],
    )
