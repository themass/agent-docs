"""关系状态存储协议。所有方法按「用户 + 角色」隔离（和画像、记忆一致）。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from companion.service.relationship.model import Relationship


class RelationshipStore(Protocol):
    async def get(self, *, owner_id: int, role_id: str) -> Relationship | None:
        """该（用户，角色）的关系行；没有互动记录返回 None（按陌生人处理）。"""
        ...

    async def bump(self, *, owner_id: int, role_id: str, delta: float, at: datetime) -> None:
        """一次有效互动：warmth += delta、interactions += 1、last_active_at = at。

        原子自增：多进程并发的回合不会互相丢增量（读-改-写在同一条 UPDATE 里）。
        """
        ...

    async def delete_user(self, *, owner_id: int) -> int:
        """账号注销：该用户的全部关系行物理删除。返回删除行数。"""
        ...
