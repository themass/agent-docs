"""CachingSessionStore: latency cache that must not survive a logout.

These tests exist so a broken revoke path fails the suite instead of looking fine
until a user notices they are still logged in on another worker.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from agentkit.redis.session import CachingSessionStore, RedisSessionStore, SessionData


class FakeRedis:
    """In-memory Redis stand-in with pub/sub enough for revoke broadcast."""

    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.published: list[tuple[str, str]] = []
        self.getex_calls = 0
        self.get_calls = 0
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        self.kv[key] = value
        self.ttls[key] = ttl
        return True

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.kv.get(key)

    async def execute_command(self, *args: Any) -> Any:
        # GETEX key EX ttl
        cmd = str(args[0]).upper()
        if cmd == "GETEX":
            self.getex_calls += 1
            key = args[1]
            if len(args) >= 4 and str(args[2]).upper() == "EX":
                self.ttls[key] = int(args[3])
            return self.kv.get(key)
        raise NotImplementedError(args)

    async def expire(self, key: str, ttl: int) -> bool:
        if key not in self.kv:
            return False
        self.ttls[key] = ttl
        return True

    async def delete(self, key: str) -> int:
        existed = 1 if key in self.kv else 0
        self.kv.pop(key, None)
        self.ttls.pop(key, None)
        return existed

    async def publish(self, channel: str, payload: str) -> int:
        self.published.append((channel, payload))
        for q in list(self._subscribers):
            await q.put({"type": "message", "channel": channel, "data": payload})
        return len(self._subscribers)

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)


class FakePubSub:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribed = False

    async def subscribe(self, channel: str) -> None:
        if not self._subscribed:
            self._redis._subscribers.append(self._q)
            self._subscribed = True
            await self._q.put({"type": "subscribe", "channel": channel, "data": 1})

    async def listen(self):
        while True:
            yield await self._q.get()


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def store(redis: FakeRedis) -> RedisSessionStore:
    return RedisSessionStore(redis, key_prefix="jc:session:", ttl_seconds=3600)


@pytest.mark.asyncio
async def test_revoke_drops_local_cache_entry(store: RedisSessionStore, redis: FakeRedis):
    cache = CachingSessionStore(store, ttl_seconds=60.0)
    await cache.create("s1", "u1")
    assert "s1" in cache._cache
    await cache.revoke("s1")
    assert "s1" not in cache._cache
    assert redis.kv == {}


@pytest.mark.asyncio
async def test_revoke_publishes_to_expected_channel(store: RedisSessionStore, redis: FakeRedis):
    cache = CachingSessionStore(store, ttl_seconds=60.0, channel="jc:session:revoked")
    await cache.create("s1", "u1")
    await cache.revoke("s1")
    assert redis.published == [("jc:session:revoked", "s1")]


@pytest.mark.asyncio
async def test_peer_cache_drops_on_broadcast(store: RedisSessionStore, redis: FakeRedis):
    """Two workers share Redis; revoke on A must clear B's in-memory hit."""
    worker_a = CachingSessionStore(store, ttl_seconds=60.0)
    worker_b = CachingSessionStore(store, ttl_seconds=60.0)
    await worker_a.start()
    await worker_b.start()
    # Let both _listen tasks reach subscribe() before we publish.
    await asyncio.sleep(0.05)
    try:
        await worker_a.create("s1", "u1")
        # Warm B from Redis so it has a positive cache entry.
        redis.getex_calls = 0
        hit = await worker_b.get_and_touch("s1")
        assert hit == SessionData(user_id="u1")
        assert "s1" in worker_b._cache
        before = redis.getex_calls

        await worker_a.revoke("s1")
        # Give the listener a turn to process the published message.
        for _ in range(20):
            if "s1" not in worker_b._cache:
                break
            await asyncio.sleep(0.01)
        assert "s1" not in worker_b._cache

        # Miss after revoke must not resurrect from Redis (deleted).
        redis.getex_calls = 0
        assert await worker_b.get_and_touch("s1") is None
        assert redis.getex_calls == 1
        # And a second call still hits negative cache without Redis.
        redis.getex_calls = 0
        assert await worker_b.get_and_touch("s1") is None
        assert redis.getex_calls == 0
        assert before >= 0  # silence unused if warm path changed
    finally:
        await worker_a.stop()
        await worker_b.stop()


@pytest.mark.asyncio
async def test_missing_session_is_negatively_cached_until_revoke(
    store: RedisSessionStore, redis: FakeRedis
):
    cache = CachingSessionStore(store, ttl_seconds=60.0)
    redis.getex_calls = 0
    assert await cache.get_and_touch("ghost") is None
    assert redis.getex_calls == 1
    redis.getex_calls = 0
    assert await cache.get_and_touch("ghost") is None
    assert redis.getex_calls == 0  # negative cache hit
    await cache.revoke("ghost")
    redis.getex_calls = 0
    assert await cache.get_and_touch("ghost") is None
    assert redis.getex_calls == 1  # cache cleared; must re-check Redis


@pytest.mark.asyncio
async def test_cache_hit_skips_store_get_and_touch(store: RedisSessionStore, redis: FakeRedis):
    cache = CachingSessionStore(store, ttl_seconds=60.0)
    await cache.create("s1", "u1")
    redis.getex_calls = 0
    assert await cache.get_and_touch("s1") == SessionData(user_id="u1")
    assert redis.getex_calls == 0


@pytest.mark.asyncio
async def test_ttl_zero_disables_cache(store: RedisSessionStore, redis: FakeRedis):
    cache = CachingSessionStore(store, ttl_seconds=0.0)
    await store.create("s1", "u1")
    redis.getex_calls = 0
    assert await cache.get_and_touch("s1") == SessionData(user_id="u1")
    assert redis.getex_calls == 1
    redis.getex_calls = 0
    assert await cache.get_and_touch("s1") == SessionData(user_id="u1")
    assert redis.getex_calls == 1  # never serves from cache


@pytest.mark.asyncio
async def test_mutation_revoke_without_publish_leaves_peer_stale(
    store: RedisSessionStore, redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
):
    """The 'must go red' check: if publish is skipped, peer keeps a live session."""
    worker_a = CachingSessionStore(store, ttl_seconds=60.0)
    worker_b = CachingSessionStore(store, ttl_seconds=60.0)
    await worker_a.start()
    await worker_b.start()
    await asyncio.sleep(0.05)
    try:
        await worker_a.create("s1", "u1")
        assert await worker_b.get_and_touch("s1") == SessionData(user_id="u1")

        async def _silent_publish(channel: str, payload: str) -> int:
            return 0  # pretend publish succeeded without delivering

        monkeypatch.setattr(store, "publish", _silent_publish)
        # Local delete still happens; Redis key gone; but B's cache stays.
        await worker_a.revoke("s1")
        await asyncio.sleep(0.05)
        # Peer still serves cached user — this is the security hole.
        redis.getex_calls = 0
        assert await worker_b.get_and_touch("s1") == SessionData(user_id="u1")
        assert redis.getex_calls == 0
    finally:
        await worker_a.stop()
        await worker_b.stop()
