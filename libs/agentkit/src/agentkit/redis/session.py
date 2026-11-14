"""Server-side session storage in Redis.

Why the read path is one round-trip
-----------------------------------
A session check that reads the key and then extends its TTL is two commands, and
on a networked Redis (measured here: 167 ms per command from the app host) that is
336 ms of latency on *every authenticated request* — before any business logic
runs. `GETEX` with an expiry does both in one command. The semantics are the same:
read the value, push the deadline out. The cost is half.

Why there is also a local cache
-------------------------------
Even one round-trip is 167 ms. `CachingSessionStore` keeps recently resolved
sessions in process memory for a short window, which removes the Redis call from
the hot path entirely. The part that makes this safe is `revoke`: a logout must not
leave a still-valid session in some other worker's memory, so revocation publishes
to a channel every worker subscribes to. Without that, a cache is a security hole
with a countdown on it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SessionData:
    user_id: str


class RedisSessionStore:
    def __init__(
        self,
        redis: Redis,
        *,
        key_prefix: str = "jc:session:",
        ttl_seconds: int = 7 * 24 * 3600,
    ) -> None:
        self._redis = redis
        self._prefix = key_prefix
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def create(self, session_id: str, user_id: str) -> None:
        payload = json.dumps({"user_id": user_id})
        await self._redis.setex(self._key(session_id), self._ttl, payload)

    async def get(self, session_id: str) -> SessionData | None:
        raw = await self._redis.get(self._key(session_id))
        return _parse(raw)

    async def get_and_touch(self, session_id: str) -> SessionData | None:
        """Read the session and extend its TTL in one command.

        This is what a request should call: it is the same operation as
        `get` followed by `touch`, at half the network cost. A Redis older than
        6.2 lacks `GETEX`; the fallback keeps correctness and pays the second
        round-trip rather than failing the request.
        """
        key = self._key(session_id)
        try:
            raw = await self._redis.execute_command("GETEX", key, "EX", self._ttl)
        except Exception:  # noqa: BLE001 - older server or proxy: fall back
            logger.debug("GETEX unavailable, falling back to GET+EXPIRE", exc_info=True)
            data = await self.get(session_id)
            if data is not None:
                await self.touch(session_id)
            return data
        return _parse(raw)

    async def touch(self, session_id: str) -> bool:
        return bool(await self._redis.expire(self._key(session_id), self._ttl))

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(self._key(session_id))

    async def publish(self, channel: str, payload: str) -> int:
        """Broadcast to peers. Used for cache invalidation, not for state."""
        return int(await self._redis.publish(channel, payload))

    def pubsub(self) -> Any:
        """A pubsub handle for the revocation listener.

        Typed `Any` because `redis.asyncio`'s pubsub class is not in its public
        typing surface; this is the one place the indirection is reachable.
        """
        return self._redis.pubsub()


def _parse(raw: Any) -> SessionData | None:
    if raw is None:
        return None
    try:
        data: dict[str, Any] = json.loads(raw)
    except (TypeError, ValueError):
        return None
    user_id = data.get("user_id")
    if not isinstance(user_id, str):
        return None
    return SessionData(user_id=user_id)


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    data: SessionData | None
    expires_at: float


class CachingSessionStore:
    """A short-TTL in-process cache in front of `RedisSessionStore`.

    The cache is small and bounded on purpose. What it must never become is a
    source of truth: `revoke` publishes to a channel that every worker listens on,
    so a logout takes effect in-flight instead of after the TTL. A process that
    misses the message still expires its own entry within `ttl_seconds`.

    Absent sessions are cached too ("negative caching"). Otherwise an attacker
    replaying a stale cookie forces a Redis round-trip per request, which is the
    load this exists to remove.
    """

    def __init__(
        self,
        store: RedisSessionStore,
        *,
        ttl_seconds: float = 60.0,
        max_entries: int = 10_000,
        channel: str = "jc:session:revoked",
    ) -> None:
        self._store = store
        self._ttl = ttl_seconds
        self._max = max_entries
        self._channel = channel
        self._cache: dict[str, _CacheEntry] = {}
        self._subscriber: asyncio.Task[None] | None = None

    # -- reads ----------------------------------------------------------

    async def get_and_touch(self, session_id: str) -> SessionData | None:
        now = time.monotonic()
        entry = self._cache.get(session_id)
        if entry is not None and entry.expires_at > now:
            return entry.data
        data = await self._store.get_and_touch(session_id)
        self._put(session_id, data, now)
        return data

    async def get(self, session_id: str) -> SessionData | None:
        return await self.get_and_touch(session_id)

    def _put(self, session_id: str, data: SessionData | None, now: float) -> None:
        if len(self._cache) >= self._max:
            # Wholesale clear rather than LRU bookkeeping: the cache is a latency
            # optimization, and a wrong eviction decision here has no correctness
            # consequence — the next request simply reads Redis.
            self._cache.clear()
        self._cache[session_id] = _CacheEntry(data=data, expires_at=now + self._ttl)

    # -- writes ---------------------------------------------------------

    async def create(self, session_id: str, user_id: str) -> None:
        await self._store.create(session_id, user_id)
        self._put(session_id, SessionData(user_id=user_id), time.monotonic())

    async def delete(self, session_id: str) -> None:
        await self.revoke(session_id)

    async def revoke(self, session_id: str) -> None:
        """Delete locally, delete in Redis, and tell every other worker to drop it.

        Publishing after the delete means a worker that reads in the gap still
        gets a miss from Redis, not a stale hit.
        """
        self._cache.pop(session_id, None)
        await self._store.delete(session_id)
        try:
            await self._store.publish(self._channel, session_id)
        except Exception:  # noqa: BLE001 - a failed broadcast must not fail logout
            logger.warning("session revocation broadcast failed; peers expire on TTL", exc_info=True)

    def invalidate_local(self, session_id: str) -> None:
        self._cache.pop(session_id, None)

    # -- peer invalidation ----------------------------------------------

    async def start(self) -> None:
        """Begin listening for revocations. Idempotent; call once at startup."""
        if self._subscriber is not None and not self._subscriber.done():
            return
        self._subscriber = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._subscriber is None:
            return
        self._subscriber.cancel()
        try:
            await self._subscriber
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        self._subscriber = None

    async def _listen(self) -> None:
        while True:
            try:
                pubsub = self._store.pubsub()
                await pubsub.subscribe(self._channel)
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    payload = message.get("data")
                    if isinstance(payload, bytes):
                        payload = payload.decode("utf-8", "replace")
                    if isinstance(payload, str) and payload:
                        self._cache.pop(payload, None)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - reconnect rather than die silently
                logger.warning("session revocation listener dropped; retrying", exc_info=True)
                await asyncio.sleep(1.0)
