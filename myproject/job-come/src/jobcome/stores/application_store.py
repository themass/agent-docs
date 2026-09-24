"""Application (投递归档) persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.interview import Application


class ApplicationStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, row: Application) -> Application:
        self._db.add(row)
        await self._db.flush()
        return row

    async def list_for_profile(self, profile_id: str, *, limit: int = 50) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.profile_id == profile_id)
            .order_by(Application.created_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())
