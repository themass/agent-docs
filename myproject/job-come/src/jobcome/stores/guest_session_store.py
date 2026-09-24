"""Guest session persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentkit.common.ids import new_id
from jobcome.models.guest import GuestSession


class GuestSessionStore:
    def __init__(
        self,
        db: AsyncSession,
        *,
        redis=None,
        guest_key_prefix: str = "jc:guest:",
        guest_ttl_days: int = 30,
    ) -> None:
        self._db = db
        self._redis = redis
        self._guest_key_prefix = guest_key_prefix
        self._guest_ttl_seconds = guest_ttl_days * 24 * 3600

    def _guest_key(self, guest_session_id: str) -> str:
        return f"{self._guest_key_prefix}{guest_session_id}"

    async def get(self, guest_session_id: str) -> GuestSession | None:
        stmt = select(GuestSession).where(GuestSession.id == guest_session_id)
        guest = (await self._db.execute(stmt)).scalar_one_or_none()
        if guest is None:
            return None
        expires_at = guest.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            return None
        return guest

    async def create(self) -> GuestSession:
        now = datetime.now(UTC)
        guest = GuestSession(
            id=new_id("gst"),
            expires_at=now + timedelta(days=self._guest_ttl_seconds // 86400),
            last_seen_at=now,
        )
        self._db.add(guest)
        await self._db.flush()
        await self._cache_guest(guest)
        return guest

    async def touch(self, guest: GuestSession) -> GuestSession:
        guest.last_seen_at = datetime.now(UTC)
        await self._db.flush()
        await self._cache_guest(guest)
        return guest

    async def mark_claimed(self, guest: GuestSession, user_id: str) -> GuestSession:
        guest.claimed_by_user_id = user_id
        guest.claimed_at = datetime.now(UTC)
        await self._db.flush()
        if self._redis is not None:
            await self._redis.delete(self._guest_key(guest.id))
        return guest

    async def _cache_guest(self, guest: GuestSession) -> None:
        if self._redis is None:
            return
        payload = json.dumps(
            {
                "guest_session_id": guest.id,
                "expires_at": guest.expires_at.isoformat(),
            }
        )
        await self._redis.setex(self._guest_key(guest.id), self._guest_ttl_seconds, payload)
