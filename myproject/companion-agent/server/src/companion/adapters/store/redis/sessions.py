"""房间会话存 Redis：多副本可见，重启不丢。

为什么是 Redis 而不是 Postgres：这些记录本来就是短命的（token 有效期 10 分钟量级），
读的时候按 session_id 直接取，不需要查询/事务；而且 agent 已经有一个 Redis 连接，
多建一张表只为存 10 分钟的数据没有收益。

键：``ca:rp:session:{session_id}`` → JSON；``ca:rp:user:{user_id}`` → 该用户的 session_id 集合。
两者同 TTL，expires_at 之后自然过期，不需要清理任务。

只用在「配了 Redis」的部署里；没有 Redis 时 app.py 继续用内存版（单实例开发）。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from companion.products.roleplay.sessions import SessionRecord

KEY_PREFIX = "ca:rp:"


def _key(session_id: str) -> str:
    return f"{KEY_PREFIX}session:{session_id}"


def _user_key(user_id: str) -> str:
    return f"{KEY_PREFIX}user:{user_id}"


class RedisSessionStore:
    """``SessionStore`` 的 Redis 实现。TTL 取 expires_at，过期的会话自动消失。"""

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def save(self, record: SessionRecord) -> None:
        ttl = max(1, int((record.expires_at - datetime.now(UTC)).total_seconds()))
        payload = json.dumps({
            "session_id": record.session_id,
            "user_id": record.user_id,
            "character_id": record.character_id,
            "room_name": record.room_name,
            "identity": record.identity,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "chat_session_id": record.chat_session_id,
        }, ensure_ascii=False)
        pipe = self._redis.pipeline()
        pipe.set(_key(record.session_id), payload, ex=ttl)
        pipe.sadd(_user_key(record.user_id), record.session_id)
        pipe.expire(_user_key(record.user_id), ttl)
        await pipe.execute()

    async def get(self, session_id: str) -> SessionRecord | None:
        raw = await self._redis.get(_key(session_id))
        if not raw:
            return None
        return _decode(raw)

    async def list_for_user(self, user_id: str) -> list[SessionRecord]:
        ids = await self._redis.smembers(_user_key(user_id))
        if not ids:
            return []
        keys = [_key(i.decode() if isinstance(i, bytes) else str(i)) for i in ids]
        raws = await self._redis.mget(*keys)
        return [r for r in (_decode(x) for x in raws if x) if r is not None]

    async def aclose(self) -> None:
        # Redis 连接由 platform 统一关闭，这里不持有独立连接
        return None


def _decode(raw: Any) -> SessionRecord | None:
    try:
        data = json.loads(raw)
        return SessionRecord(
            session_id=data["session_id"],
            user_id=data["user_id"],
            character_id=data["character_id"],
            room_name=data["room_name"],
            identity=data["identity"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            chat_session_id=data.get("chat_session_id"),
        )
    except (ValueError, KeyError, TypeError):
        # 坏数据当不存在：一次读失败不该让建房间整条链路挂掉
        return None
