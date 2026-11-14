"""Redis client factory."""

from __future__ import annotations

from redis.asyncio import Redis


def redis_from_url(url: str, *, decode_responses: bool = True) -> Redis:
    return Redis.from_url(url, decode_responses=decode_responses)
