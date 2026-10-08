"""Application funnel: list, upsert after fit, user-driven status."""

from __future__ import annotations

from datetime import date

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.exceptions import AppError, ForbiddenError, NotFoundError
from jobcome.models.enums import ApplicationStatus
from jobcome.models.interview import Application
from jobcome.schemas.job import ApplicationPatchRequest, ApplicationResponse
from jobcome.services.profile_service import ProfileService
from jobcome.stores.application_store import ApplicationStore
from jobcome.stores.job_store import JobStore

_FUNNEL_STATUSES = frozenset(s.value for s in ApplicationStatus)
_KEEP_ON_APPLY = frozenset(
    {
        ApplicationStatus.APPLIED.value,
        ApplicationStatus.INTERVIEWING.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.OFFER.value,
    }
)


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
        return [await self._to_response(row) for row in rows]

    async def upsert_evaluated(
        self,
        profile_id: str,
        job_id: str,
        *,
        actor: UserActor,
    ) -> Application:
        existing = await self._apps.get_by_profile_job(profile_id, job_id)
        if existing is not None:
            return existing
        row = Application(
            id=new_id("appl"),
            job_id=job_id,
            profile_id=profile_id,
            user_id=actor.user_id,
            status=ApplicationStatus.EVALUATED.value,
            user_marked=True,
        )
        await self._apps.create(row)
        return row

    async def mark_applied(
        self,
        profile_id: str,
        job_id: str,
        *,
        actor: UserActor,
        resume_variant_id: str | None,
        note: str | None = None,
    ) -> Application:
        row = await self._apps.get_by_profile_job(profile_id, job_id)
        if row is None:
            row = Application(
                id=new_id("appl"),
                job_id=job_id,
                profile_id=profile_id,
                user_id=actor.user_id,
                user_marked=True,
            )
            await self._apps.create(row)
        if row.user_id != actor.user_id:
            raise ForbiddenError("Not your application")
        if row.status not in _KEEP_ON_APPLY:
            row.status = ApplicationStatus.APPLIED.value
        row.applied_at = row.applied_at or date.today()
        if resume_variant_id:
            row.resume_variant_id = resume_variant_id
        if note:
            row.note = note
        await self._apps.save(row)
        return row

    async def patch(
        self,
        profile_id: str,
        application_id: str,
        *,
        actor: UserActor,
        body: ApplicationPatchRequest,
    ) -> ApplicationResponse:
        await self._profiles.get(profile_id, actor=actor)
        row = await self._apps.get_by_id(application_id)
        if row is None or row.profile_id != profile_id:
            raise NotFoundError("Application not found")
        if row.user_id != actor.user_id:
            raise ForbiddenError("Not your application")

        if body.status is not None:
            if body.status not in _FUNNEL_STATUSES:
                raise AppError("Invalid application status", code="invalid_request")
            row.status = body.status
            if body.status == ApplicationStatus.APPLIED.value and row.applied_at is None:
                row.applied_at = date.today()
        if body.note is not None:
            row.note = body.note or None
        if body.follow_up_on is not None:
            if body.follow_up_on == "":
                row.follow_up_on = None
            else:
                try:
                    row.follow_up_on = date.fromisoformat(body.follow_up_on)
                except ValueError as exc:
                    raise AppError(
                        "follow_up_on must be YYYY-MM-DD",
                        code="invalid_request",
                    ) from exc
        await self._apps.save(row)
        await self._db.commit()
        await self._db.refresh(row)
        return await self._to_response(row)

    async def _to_response(self, row: Application) -> ApplicationResponse:
        job = await self._jobs.get_by_id(row.job_id)
        return ApplicationResponse(
            id=row.id,
            job_id=row.job_id,
            profile_id=row.profile_id,
            resume_variant_id=row.resume_variant_id,
            applied_at=row.applied_at.isoformat() if row.applied_at else None,
            follow_up_on=row.follow_up_on.isoformat() if row.follow_up_on else None,
            status=row.status or ApplicationStatus.EVALUATED.value,
            note=row.note,
            company=job.company if job else None,
            title=job.title if job else None,
            fit_score=job.fit_score if job else None,
            fit_recommendation=job.fit_recommendation if job else None,
        )
