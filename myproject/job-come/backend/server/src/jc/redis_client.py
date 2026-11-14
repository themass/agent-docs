"""Shared Redis connection for JC."""

from __future__ import annotations

from functools import lru_cache

from agentkit.redis import RedisSessionStore, redis_from_url
from agentkit.redis.session import CachingSessionStore
from redis.asyncio import Redis

from jc.config import settings


@lru_cache
def get_redis() -> Redis:
    return redis_from_url(settings.jc_redis_url)


def redis_key_prefix(namespace: str) -> str:
    """Return the configured JC Redis prefix for one namespace."""
    normalized_namespace = namespace.strip(":")
    if not normalized_namespace:
        raise ValueError("Redis namespace must not be empty")
    base = settings.jc_redis_key_prefix.strip()
    if not base:
        raise ValueError("JC_REDIS_KEY_PREFIX must not be empty")
    return f"{base.rstrip(':')}:{normalized_namespace}:"


def redis_key(namespace: str, identifier: str) -> str:
    """Build one JC-owned Redis key; do not concatenate raw prefixes elsewhere."""
    return f"{redis_key_prefix(namespace)}{identifier}"


@lru_cache
def _session_store() -> CachingSessionStore:
    """The process-wide session store, cached in memory for a short window.

    Measured on production: Redis is 167 ms away, and the request path used to do
    `GET` + `EXPIRE` — 336 ms of pure latency on every authenticated request.
    `GETEX` halves that; the local cache removes it from the hot path entirely.

    The TTL is 60 seconds, not minutes, because it bounds how long a logout can
    fail to take effect in another worker. `revoke` publishes to every worker, so
    the real window is the broadcast latency; this TTL is the backstop for a
    worker that missed the message.
    """
    ttl = settings.jc_session_ttl_days * 24 * 3600
    return CachingSessionStore(
        RedisSessionStore(
            get_redis(),
            key_prefix=redis_key_prefix("session"),
            ttl_seconds=ttl,
        ),
        ttl_seconds=settings.jc_session_cache_seconds,
        max_entries=settings.jc_session_cache_max_entries,
        channel=redis_key_prefix("session") + "revoked",
    )


def get_session_store() -> CachingSessionStore:
    return _session_store()
