"""Job persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.job import Job


class JobStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, job_id: str) -> Job | None:
        return await self._db.get(Job, job_id)

    async def list_for_profile(self, profile_id: str, *, limit: int = 50) -> list[Job]:
        stmt = (
            select(Job)
            .where(Job.profile_id == profile_id, Job.status == "active")
            .order_by(Job.updated_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def create(self, job: Job) -> Job:
        self._db.add(job)
        await self._db.flush()
        return job

    async def save(self, job: Job) -> Job:
        await self._db.flush()
        return job
