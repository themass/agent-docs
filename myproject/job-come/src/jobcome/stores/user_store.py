"""User persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agentkit.common.ids import new_id
from jobcome.models.enums import ElevationLevel, UserStatus
from jobcome.models.user import User, UserMeta


class UserStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.meta))
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
            .options(selectinload(User.meta))
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str | None = None,
    ) -> User:
        user = User(
            id=new_id("usr"),
            email=email.lower(),
            password_hash=password_hash,
            status=UserStatus.ACTIVE,
        )
        user.meta = UserMeta(
            user_id=user.id,
            display_name=display_name,
            default_elevation_level=ElevationLevel.ELEVATED,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    async def update_password(self, user: User, password_hash: str) -> User:
        from datetime import UTC, datetime

        user.password_hash = password_hash
        user.password_changed_at = datetime.now(UTC)
        await self._db.flush()
        return user

    async def mark_email_verified(self, user: User) -> User:
        from datetime import UTC, datetime

        user.email_verified_at = datetime.now(UTC)
        await self._db.flush()
        return user

    async def get_or_create_meta(self, user_id: str) -> UserMeta:
        user = await self.get_by_id(user_id)
        if user is None:
            raise ValueError(f"User not found: {user_id}")
        if user.meta is None:
            user.meta = UserMeta(
                user_id=user_id,
                default_elevation_level=ElevationLevel.ELEVATED,
            )
            self._db.add(user.meta)
            await self._db.flush()
        return user.meta
