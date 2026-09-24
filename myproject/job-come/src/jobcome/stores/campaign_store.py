"""Campaign persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.job import Campaign


class CampaignStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_for_profile(self, profile_id: str) -> Campaign | None:
        stmt = select(Campaign).where(Campaign.profile_id == profile_id).limit(1)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create(self, row: Campaign) -> Campaign:
        self._db.add(row)
        await self._db.flush()
        return row

    async def save(self, row: Campaign) -> Campaign:
        await self._db.flush()
        return row
