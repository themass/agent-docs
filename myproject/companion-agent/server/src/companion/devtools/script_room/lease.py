"""剧本房租赁：同一 case_id 在 TTL 内落到同一个 script- 房间。

Phone HTTP 与 CLI 都调 ``attach(case_id)``，顺序无关地会师同一房间。
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from typing import Any, Protocol

from companion.service.room.sessions import SCRIPT_ROOM_PREFIX, script_room_name_for

LEASE_KEY_PREFIX = "ca:script:lease:"
DEFAULT_TTL_SEC = 600


def _lease_key(case_id: str) -> str:
    return f"{LEASE_KEY_PREFIX}{case_id}"


class ScriptRoomLease(Protocol):
    async def attach(self, case_id: str) -> str:
        """返回（或复用）该 case 的房间名。"""
        ...


@dataclass
class InMemoryScriptRoomLease:
    """dict + Lock，单测与无 Redis 开发用。"""

    ttl_sec: int = DEFAULT_TTL_SEC
    _rooms: dict[str, str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def attach(self, case_id: str) -> str:
        if not case_id:
            raise ValueError("case_id 不能为空")
        async with self._lock:
            existing = self._rooms.get(case_id)
            if existing is not None:
                return existing
            short_id = secrets.token_urlsafe(8)
            room = script_room_name_for(case_id, short_id)
            assert room.startswith(SCRIPT_ROOM_PREFIX)
            self._rooms[case_id] = room
            return room


@dataclass
class RedisScriptRoomLease:
    """Redis SET NX + EX：多副本共享，TTL 到点自动释放。"""

    redis: Any
    ttl_sec: int = DEFAULT_TTL_SEC

    async def attach(self, case_id: str) -> str:
        if not case_id:
            raise ValueError("case_id 不能为空")
        key = _lease_key(case_id)
        existing = await self.redis.get(key)
        if existing:
            return existing.decode() if isinstance(existing, bytes) else str(existing)
        short_id = secrets.token_urlsafe(8)
        room = script_room_name_for(case_id, short_id)
        # SET NX：并发抢占时输的一方读回赢家写入的房间名
        ok = await self.redis.set(key, room, nx=True, ex=self.ttl_sec)
        if ok:
            return room
        raced = await self.redis.get(key)
        if not raced:
            # 极窄窗口：NX 失败后 key 又过期——再写一次
            await self.redis.set(key, room, ex=self.ttl_sec)
            return room
        return raced.decode() if isinstance(raced, bytes) else str(raced)
