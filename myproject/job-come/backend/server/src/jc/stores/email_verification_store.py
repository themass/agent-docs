"""Single-use email-verification credentials stored in Redis."""

from __future__ import annotations

import secrets
from typing import Literal

from redis.asyncio import Redis

from jc.redis_client import redis_key
from jc.utils.security_tokens import hash_token

VerificationCodeResult = Literal["verified", "invalid", "expired", "locked"]


class EmailVerificationStore:
    """Persist one link token and one four-digit code per user with a shared TTL."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _token_key(token_hash: str) -> str:
        return redis_key("email-verify", token_hash)

    @staticmethod
    def _user_key(user_id: str) -> str:
        return redis_key("email-verify-user", user_id)

    @staticmethod
    def _code_key(user_id: str) -> str:
        return redis_key("email-verify-code", user_id)

    @staticmethod
    def _attempt_key(user_id: str) -> str:
        return redis_key("email-verify-attempt", user_id)

    @staticmethod
    def _decode(value: str | bytes | None) -> str | None:
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    async def save(self, *, user_id: str, plain_token: str, ttl_seconds: int) -> None:
        """Save a link token only (legacy internal helper kept for focused callers)."""
        token_hash = hash_token(plain_token)
        await self._redis.set(self._token_key(token_hash), user_id, ex=ttl_seconds)

    async def consume(self, plain_token: str) -> str | None:
        """Consume a link token only (legacy internal helper)."""
        token_hash = hash_token(plain_token)
        key = self._token_key(token_hash)
        user_id = self._decode(await self._redis.get(key))
        if user_id is None:
            return None
        await self._redis.delete(key)
        return user_id

    async def issue(
        self,
        *,
        user_id: str,
        plain_token: str,
        verification_code: str,
        ttl_seconds: int,
    ) -> None:
        """Replace all prior credentials so an older link/code cannot be reused."""
        await self.invalidate_for_user(user_id)
        token_hash = hash_token(plain_token)
        code_hash = hash_token(verification_code)
        await self._redis.set(self._token_key(token_hash), user_id, ex=ttl_seconds)
        await self._redis.set(self._user_key(user_id), token_hash, ex=ttl_seconds)
        await self._redis.set(self._code_key(user_id), code_hash, ex=ttl_seconds)
        await self._redis.set(self._attempt_key(user_id), 0, ex=ttl_seconds)

    async def consume_token(self, plain_token: str) -> str | None:
        token_hash = hash_token(plain_token)
        user_id = self._decode(await self._redis.get(self._token_key(token_hash)))
        if user_id is None:
            return None
        await self.invalidate_for_user(user_id)
        return user_id

    async def verify_code(
        self,
        *,
        user_id: str,
        verification_code: str,
        max_attempts: int,
    ) -> VerificationCodeResult:
        expected_hash = self._decode(await self._redis.get(self._code_key(user_id)))
        if expected_hash is None:
            return "expired"

        attempts = await self._redis.incr(self._attempt_key(user_id))
        if attempts > max_attempts:
            await self.invalidate_for_user(user_id)
            return "locked"

        if not secrets.compare_digest(expected_hash, hash_token(verification_code)):
            return "invalid"

        await self.invalidate_for_user(user_id)
        return "verified"

    async def invalidate_for_user(self, user_id: str) -> None:
        token_hash = self._decode(await self._redis.get(self._user_key(user_id)))
        keys = [self._user_key(user_id), self._code_key(user_id), self._attempt_key(user_id)]
        if token_hash:
            keys.append(self._token_key(token_hash))
        await self._redis.delete(*keys)
