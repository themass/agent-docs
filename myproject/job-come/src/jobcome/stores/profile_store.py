"""Profile persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jobcome.models.enums import OwnerKind
from jobcome.models.profile import Profile, ProfileSource


class ProfileStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, profile_id: str, *, with_sources: bool = False) -> Profile | None:
        stmt = select(Profile).where(Profile.id == profile_id, Profile.deleted_at.is_(None))
        if with_sources:
            stmt = stmt.options(selectinload(Profile.sources))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_active_for_guest(self, guest_session_id: str) -> Profile | None:
        stmt = (
            select(Profile)
            .where(
                Profile.guest_session_id == guest_session_id,
                Profile.deleted_at.is_(None),
            )
            .order_by(Profile.updated_at.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_active_for_user(self, user_id: str) -> Profile | None:
        stmt = (
            select(Profile)
            .where(
                Profile.user_id == user_id,
                Profile.deleted_at.is_(None),
            )
            .order_by(Profile.updated_at.desc())
            .limit(1)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[Profile]:
        stmt = (
            select(Profile)
            .where(Profile.user_id == user_id, Profile.deleted_at.is_(None))
            .order_by(Profile.updated_at.desc())
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_for_user(self, user_id: str, profile_id: str) -> Profile | None:
        stmt = select(Profile).where(
            Profile.id == profile_id,
            Profile.user_id == user_id,
            Profile.deleted_at.is_(None),
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create(self, profile: Profile) -> Profile:
        self._db.add(profile)
        await self._db.flush()
        return profile

    async def add_source(self, source: ProfileSource) -> ProfileSource:
        self._db.add(source)
        await self._db.flush()
        return source

    async def transfer_guest_to_user(self, profile: Profile, user_id: str) -> Profile:
        profile.user_id = user_id
        profile.guest_session_id = None
        profile.owner_kind = OwnerKind.USER
        await self._db.flush()
        return profile

    async def soft_delete(self, profile: Profile) -> Profile:
        from datetime import UTC, datetime

        profile.deleted_at = datetime.now(UTC)
        await self._db.flush()
        return profile
