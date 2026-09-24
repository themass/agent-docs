"""Password reset token persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentkit.common.ids import new_id
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.guest import PasswordResetToken
from jobcome.utils.security_tokens import hash_token


class PasswordResetStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, *, user_id: str, plain_token: str, ttl_hours: int) -> PasswordResetToken:
        row = PasswordResetToken(
            id=new_id("prt"),
            user_id=user_id,
            token_hash=hash_token(plain_token),
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
            used_at=None,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def invalidate_active_for_user(self, user_id: str) -> None:
        now = datetime.now(UTC)
        await self._db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .values(used_at=now)
        )

    async def get_valid(self, plain_token: str) -> PasswordResetToken | None:
        token_hash = hash_token(plain_token)
        now = datetime.now(UTC)
        stmt = (
            select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def mark_used(self, row: PasswordResetToken) -> None:
        row.used_at = datetime.now(UTC)
        await self._db.flush()
