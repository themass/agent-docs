"""Guest asset claim on login/register."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.profile import Profile
from jobcome.schemas.auth import MergeConflictProfileSummary, MergeConflictResponse
from jobcome.stores.guest_session_store import GuestSessionStore
from jobcome.stores.profile_store import ProfileStore


@dataclass(frozen=True, slots=True)
class ClaimResult:
    active_profile_id: str | None
    merge_conflict: MergeConflictResponse | None


class GuestMigrationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._guests = GuestSessionStore(db)
        self._profiles = ProfileStore(db)

    async def claim(self, guest_session_id: str | None, user_id: str) -> ClaimResult:
        if not guest_session_id:
            profile = await self._profiles.get_active_for_user(user_id)
            return ClaimResult(
                active_profile_id=profile.id if profile else None,
                merge_conflict=None,
            )

        guest = await self._guests.get(guest_session_id)
        if guest is None or guest.claimed_by_user_id is not None:
            profile = await self._profiles.get_active_for_user(user_id)
            return ClaimResult(
                active_profile_id=profile.id if profile else None,
                merge_conflict=None,
            )

        guest_profile = await self._profiles.get_active_for_guest(guest_session_id)
        user_profile = await self._profiles.get_active_for_user(user_id)

        if guest_profile and user_profile:
            merge_conflict = self._build_merge_conflict(guest_profile, user_profile)
            return ClaimResult(active_profile_id=user_profile.id, merge_conflict=merge_conflict)

        active_profile_id: str | None
        if guest_profile and not user_profile:
            transferred = await self._profiles.transfer_guest_to_user(guest_profile, user_id)
            active_profile_id = transferred.id
        elif user_profile:
            active_profile_id = user_profile.id
        else:
            active_profile_id = None

        await self._guests.mark_claimed(guest, user_id)
        return ClaimResult(active_profile_id=active_profile_id, merge_conflict=None)

    async def resolve(
        self,
        user_id: str,
        guest_session_id: str,
        choice: str,
    ) -> ClaimResult:
        guest = await self._guests.get(guest_session_id)
        if guest is None:
            raise ValueError("Guest session not found")

        guest_profile = await self._profiles.get_active_for_guest(guest_session_id)
        account_profile = await self._profiles.get_active_for_user(user_id)
        if guest_profile is None or account_profile is None:
            profile = account_profile or guest_profile
            await self._guests.mark_claimed(guest, user_id)
            return ClaimResult(
                active_profile_id=profile.id if profile else None,
                merge_conflict=None,
            )

        if choice == "keep_guest":
            await self._profiles.soft_delete(account_profile)
            await self._profiles.transfer_guest_to_user(guest_profile, user_id)
            active_profile_id = guest_profile.id
        else:
            await self._profiles.soft_delete(guest_profile)
            active_profile_id = account_profile.id

        await self._guests.mark_claimed(guest, user_id)
        return ClaimResult(active_profile_id=active_profile_id, merge_conflict=None)

    @staticmethod
    def _build_merge_conflict(
        guest_profile: Profile,
        user_profile: Profile,
    ) -> MergeConflictResponse:
        return MergeConflictResponse(
            guest_profile=MergeConflictProfileSummary(
                id=guest_profile.id,
                contact_name=guest_profile.contact_name,
                updated_at=guest_profile.updated_at.isoformat(),
            ),
            account_profile=MergeConflictProfileSummary(
                id=user_profile.id,
                contact_name=user_profile.contact_name,
                updated_at=user_profile.updated_at.isoformat(),
            ),
        )
