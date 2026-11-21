"""关系状态的 SQL 实现。协议见 port.py，语义见 model.py 与设计文档。

bump 是单条条件 UPDATE（读-改-写收在 SQL 里）：两个 worker 同时给同一
（用户，角色）加分时不丢增量，也不需要在回合路径上拿 FOR UPDATE。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from companion.db.schema import relationship
from companion.service.relationship.model import Relationship


def _naive(value: datetime | None) -> datetime | None:
    return value.astimezone(value.tzinfo).replace(tzinfo=None) if value is not None and value.tzinfo else value


def _row(r) -> Relationship:
    return Relationship(owner_id=int(r["owner_id"]), role_id=r["role_id"], warmth=float(r["warmth"]),
                        interactions=int(r["interactions"]), last_active_at=r["last_active_at"])


class SqlRelationshipStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(self, *, owner_id: int, role_id: str) -> Relationship | None:
        async with self._engine.connect() as conn:
            r = (await conn.execute(select(relationship).where(
                relationship.c.owner_id == owner_id, relationship.c.role_id == role_id))).first()
        return _row(r) if r else None

    async def bump(self, *, owner_id: int, role_id: str, delta: float, at: datetime) -> None:
        at = _naive(at)
        async with self._engine.begin() as conn:
            existing = (await conn.execute(select(relationship.c.owner_id).where(
                relationship.c.owner_id == owner_id, relationship.c.role_id == role_id))).first()
            if existing is None:
                await conn.execute(insert(relationship).values(
                    owner_id=owner_id, role_id=role_id, warmth=delta, interactions=1,
                    last_active_at=at, created_at=at, updated_at=at))
            else:
                await conn.execute(update(relationship).where(
                    relationship.c.owner_id == owner_id, relationship.c.role_id == role_id)
                    .values(warmth=relationship.c.warmth + delta, interactions=relationship.c.interactions + 1,
                            last_active_at=at, updated_at=at))

    async def delete_user(self, *, owner_id: int) -> int:
        async with self._engine.begin() as conn:
            res = await conn.execute(delete(relationship).where(relationship.c.owner_id == owner_id))
        return res.rowcount
