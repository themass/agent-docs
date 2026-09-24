"""Email verification tokens in Redis."""

from __future__ import annotations

from redis.asyncio import Redis

from jobcome.utils.security_tokens import hash_token


class EmailVerificationStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _key(token_hash: str) -> str:
        return f"jc:email_verify:{token_hash}"

    async def save(self, *, user_id: str, plain_token: str, ttl_seconds: int) -> None:
        token_hash = hash_token(plain_token)
        await self._redis.set(self._key(token_hash), user_id, ex=ttl_seconds)

    async def consume(self, plain_token: str) -> str | None:
        token_hash = hash_token(plain_token)
        key = self._key(token_hash)
        user_id = await self._redis.get(key)
        if user_id is None:
            return None
        await self._redis.delete(key)
        if isinstance(user_id, bytes):
            return user_id.decode("utf-8")
        return str(user_id)
