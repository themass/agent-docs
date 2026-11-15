"""Profile persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jc.models.enums import OwnerKind
from jc.models.profile import Profile, ProfileSource


class ProfileStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, profile_id: str, *, with_sources: bool = False) -> Profile | None:
        stmt = select(Profile).where(Profile.id == profile_id, Profile.deleted_at.is_(None))
        if with_sources:
            stmt = stmt.options(selectinload(Profile.sources))
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_for_update(self, profile_id: str) -> Profile | None:
        """The profile, locked until this transaction ends.

        Every payload write does read-modify-write on `version`:
        `profile.version += 1` after loading the row with `get_by_id`, which takes
        no lock. Two concurrent writers therefore read the same version and both
        compute the same successor — and because every payload write also inserts a
        `jc_profile_snapshot` row keyed by `(profile_id, version_after)`, the second
        one dies on the unique index.

        Measured on production during a test run: 21 `UniqueViolation`s, all on
        `Key (profile_id, version_after)=...`, across five profiles, with
        `PendingRollbackError` following each one — the session was left unusable for
        the rest of the request, which is why unrelated endpoints then timed out.

        `FOR NO KEY UPDATE`, not `FOR UPDATE`: the latter conflicts with the
        `FOR KEY SHARE` that inserting into any child table takes on this row, and
        holds up every writer that references the profile. This lock still excludes
        other version writers, which is all the increment needs.
        """
        stmt = (
            select(Profile)
            .where(Profile.id == profile_id, Profile.deleted_at.is_(None))
            .with_for_update(key_share=True)
        )
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

    async def profile_counts_by_user(self, user_ids: list[str]) -> dict[str, int]:
        if not user_ids:
            return {}
        stmt = (
            select(Profile.user_id, func.count())
            .where(Profile.user_id.in_(user_ids), Profile.deleted_at.is_(None))
            .group_by(Profile.user_id)
        )
        rows = (await self._db.execute(stmt)).all()
        return {user_id: int(count) for user_id, count in rows}

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
