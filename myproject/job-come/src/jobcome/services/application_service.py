"""Application list service."""

from __future__ import annotations

from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.schemas.job import ApplicationResponse
from jobcome.services.profile_service import ProfileService
from jobcome.stores.application_store import ApplicationStore
from jobcome.stores.job_store import JobStore


class ApplicationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._apps = ApplicationStore(db)
        self._jobs = JobStore(db)
        self._profiles = ProfileService(db)

    async def list_for_profile(
        self,
        profile_id: str,
        *,
        actor: Actor,
    ) -> list[ApplicationResponse]:
        await self._profiles.get(profile_id, actor=actor)
        rows = await self._apps.list_for_profile(profile_id)
        if isinstance(actor, UserActor):
            rows = [r for r in rows if r.user_id == actor.user_id]
        out: list[ApplicationResponse] = []
        for row in rows:
            job = await self._jobs.get_by_id(row.job_id)
            out.append(
                ApplicationResponse(
                    id=row.id,
                    job_id=row.job_id,
                    profile_id=row.profile_id,
                    resume_variant_id=row.resume_variant_id,
                    applied_at=row.applied_at.isoformat() if row.applied_at else None,
                    note=row.note,
                    company=job.company if job else None,
                    title=job.title if job else None,
                )
            )
        return out
