"""剧本房租赁：同一 case_id 在 TTL 内落到同一个 script- 房间。

Phone HTTP 与 CLI 都调 ``attach(case_id)``，顺序无关地会师同一房间。
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from companion.service.room.sessions import SCRIPT_ROOM_PREFIX, script_room_name_for

LEASE_KEY_PREFIX = "ca:script:lease:"
DEFAULT_TTL_SEC = 600
# Redis NX 竞争后 key 又过期的极窄窗口：有界重试，避免死循环
_REDIS_ATTACH_MAX_ATTEMPTS = 8


def _lease_key(case_id: str) -> str:
    return f"{LEASE_KEY_PREFIX}{case_id}"


class ScriptRoomLease(Protocol):
    async def attach(self, case_id: str) -> str:
        """返回（或复用）该 case 的房间名。"""
        ...


@dataclass
class InMemoryScriptRoomLease:
    """dict + Lock，单测与无 Redis 开发用；条目按 ttl_sec 过期。"""

    ttl_sec: int = DEFAULT_TTL_SEC
    _rooms: dict[str, tuple[str, float]] = field(default_factory=dict)  # case_id → (room, deadline)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _now: Any = field(default=time.monotonic, repr=False)

    async def attach(self, case_id: str) -> str:
        if not case_id:
            raise ValueError("case_id 不能为空")
        now = float(self._now())
        async with self._lock:
            existing = self._rooms.get(case_id)
            if existing is not None:
                room, deadline = existing
                if now < deadline:
                    return room
                del self._rooms[case_id]
            short_id = secrets.token_urlsafe(8)
            room = script_room_name_for(case_id, short_id)
            assert room.startswith(SCRIPT_ROOM_PREFIX)
            self._rooms[case_id] = (room, now + self.ttl_sec)
            return room


@dataclass
class RedisScriptRoomLease:
    """Redis SET NX + EX：多副本共享，TTL 到点自动释放。

    只返回「成功写入」或「读到已存在」的房间名；NX 竞争输了且 key 已空时，
    重新 SET NX，绝不无条件 SET 后返回本地生成但未独占成功的名字。
    """

    redis: Any
    ttl_sec: int = DEFAULT_TTL_SEC

    async def attach(self, case_id: str) -> str:
        if not case_id:
            raise ValueError("case_id 不能为空")
        key = _lease_key(case_id)
        for _ in range(_REDIS_ATTACH_MAX_ATTEMPTS):
            existing = await self.redis.get(key)
            if existing:
                return existing.decode() if isinstance(existing, bytes) else str(existing)
            short_id = secrets.token_urlsafe(8)
            room = script_room_name_for(case_id, short_id)
            ok = await self.redis.set(key, room, nx=True, ex=self.ttl_sec)
            if ok:
                return room
            # NX 失败：读回赢家；若极窄窗口内 key 又过期，下一轮继续 SET NX
            raced = await self.redis.get(key)
            if raced:
                return raced.decode() if isinstance(raced, bytes) else str(raced)
        raise RuntimeError(f"script lease attach 重试耗尽：case_id={case_id}")
