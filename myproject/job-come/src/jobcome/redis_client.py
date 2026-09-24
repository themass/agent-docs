"""Shared Redis connection for JobCome."""

from __future__ import annotations

from functools import lru_cache

from agentkit.redis import RedisSessionStore, redis_from_url
from redis.asyncio import Redis

from jobcome.config import settings


@lru_cache
def get_redis() -> Redis:
    return redis_from_url(settings.job_come_redis_url)


def get_session_store() -> RedisSessionStore:
    ttl = settings.job_come_session_ttl_days * 24 * 3600
    return RedisSessionStore(get_redis(), ttl_seconds=ttl)
