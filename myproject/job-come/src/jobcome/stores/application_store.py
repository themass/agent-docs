"""Application (投递归档) persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.interview import Application


class ApplicationStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, row: Application) -> Application:
        self._db.add(row)
        await self._db.flush()
        return row

    async def save(self, row: Application) -> Application:
        await self._db.flush()
        return row

    async def get_by_id(self, application_id: str) -> Application | None:
        return await self._db.get(Application, application_id)

    async def get_by_profile_job(self, profile_id: str, job_id: str) -> Application | None:
        stmt = select(Application).where(
            Application.profile_id == profile_id,
            Application.job_id == job_id,
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def count_status(self, profile_id: str, status: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Application)
            .where(Application.profile_id == profile_id, Application.status == status)
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def list_for_profile(self, profile_id: str, *, limit: int = 200) -> list[Application]:
        stmt = (
            select(Application)
            .where(Application.profile_id == profile_id)
            .order_by(Application.created_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())
