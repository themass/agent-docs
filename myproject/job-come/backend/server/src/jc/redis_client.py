"""Shared Redis connection for JC."""

from __future__ import annotations

from functools import lru_cache

from agentkit.redis import RedisSessionStore, redis_from_url
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


def get_session_store() -> RedisSessionStore:
    ttl = settings.jc_session_ttl_days * 24 * 3600
    return RedisSessionStore(
        get_redis(),
        key_prefix=redis_key_prefix("session"),
        ttl_seconds=ttl,
    )
