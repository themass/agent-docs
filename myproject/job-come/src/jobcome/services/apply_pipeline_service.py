"""Apply pipeline: fit → job-bound elevate → review → export → archive (ai-job-search /apply)."""

from __future__ import annotations

from datetime import UTC, date

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.observability.events import log_product_event
from jobcome.models.enums import ElevationLevel, ExportFormat, JobTag
from jobcome.models.interview import Application
from jobcome.schemas.job import (
    ApplyPipelineRequest,
    ApplyPipelineResponse,
    FitScoreRequest,
    JobParseRequest,
)
from jobcome.schemas.resume import ExportRequest
from jobcome.services.job_service import JobService
from jobcome.services.profile_service import ProfileService
from jobcome.services.resume_service import ResumeService
from jobcome.stores.application_store import ApplicationStore
from jobcome.stores.job_store import JobStore


class ApplyPipelineService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._jobs = JobService(db)
        self._resumes = ResumeService(db)
        self._profiles = ProfileService(db)
        self._applications = ApplicationStore(db)
        self._job_store = JobStore(db)

    async def run(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: ApplyPipelineRequest,
        trace_id: str | None = None,
    ) -> ApplyPipelineResponse:
        if not isinstance(actor, UserActor):
            raise AppError("Login required for apply pipeline", code="login_required")

        user_id = actor.user_id
        log_product_event(
            "apply_pipeline_start",
            trace_id=trace_id,
            user_id=user_id,
            profile_id=profile_id,
            job_id=body.job_id,
        )

        job_id = body.job_id
        if not job_id:
            if not body.raw_text:
                raise AppError("Provide job_id or raw_text", code="invalid_request")
            parsed = await self._jobs.parse_jd(
                profile_id,
                actor=actor,
                body=JobParseRequest(
                    raw_text=body.raw_text,
                    source_url=body.source_url,
                    save=True,
                ),
            )
            job_id = parsed.id
            if not job_id:
                raise AppError("Failed to save job", code="job_save_failed")

        fit = await self._jobs.fit_score(
            profile_id,
            actor=actor,
            body=FitScoreRequest(job_id=job_id),
        )
        log_product_event(
            "apply_pipeline_fit",
            trace_id=trace_id,
            user_id=user_id,
            profile_id=profile_id,
            job_id=job_id,
            score=fit.score,
            recommendation=fit.recommendation,
        )

        draft = await self._resumes.elevate(
            profile_id,
            actor=actor,
            elevation_level=body.elevation_level,
            job_id=job_id,
        )

        export_resp = None
        application_id = None
        try:
            export_resp = await self._resumes.export(
                profile_id,
                actor=actor,
                body=ExportRequest(
                    format=ExportFormat(body.export_format),
                    elevation_level=ElevationLevel(body.elevation_level),
                    draft_id=draft.id,
                ),
            )
        except AppError as exc:
            if exc.code != "reviewer_failed":
                raise
            log_product_event(
                "apply_pipeline_reviewer_failed",
                trace_id=trace_id,
                user_id=user_id,
                profile_id=profile_id,
                job_id=job_id,
                error=exc.message,
            )
            return ApplyPipelineResponse(
                job_id=job_id,
                fit=fit,
                draft=draft.model_dump(mode="json"),
                export={"error": exc.message, "code": exc.code},
                application_id=None,
            )

        if body.create_application and export_resp and export_resp.status == "done":
            app = Application(
                id=new_id("appl"),
                job_id=job_id,
                profile_id=profile_id,
                user_id=actor.user_id,
                resume_variant_id=draft.id,
                applied_at=date.today(),
                user_marked=True,
                note=f"export:{export_resp.id}",
            )
            await self._applications.create(app)
            application_id = app.id
            job = await self._job_store.get_by_id(job_id)
            if job is not None:
                job.tag = JobTag.TARGET if fit.recommendation == "go" else JobTag.WARMUP
                await self._job_store.save(job)
            await self._db.commit()

        log_product_event(
            "apply_pipeline_done",
            trace_id=trace_id,
            user_id=user_id,
            profile_id=profile_id,
            job_id=job_id,
            application_id=application_id,
            export_status=export_resp.status if export_resp else None,
        )
        return ApplyPipelineResponse(
            job_id=job_id,
            fit=fit,
            draft=draft.model_dump(mode="json"),
            export=export_resp.model_dump(mode="json") if export_resp else None,
            application_id=application_id,
        )

    async def prep_context(self, profile_id: str, job_id: str, *, actor: Actor) -> dict:
        """Interview prep pack (ai-job-search /interview)."""
        profile = await self._profiles.get(profile_id, actor=actor)
        job = await self._job_store.get_by_id(job_id)
        if job is None or job.profile_id != profile_id:
            raise NotFoundError("Job not found")
        return {
            "profile_summary": (profile.payload.summary or "")[:500],
            "job": {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "requirements": job.requirements,
                "fit_score": job.fit_score,
                "fit_recommendation": job.fit_recommendation,
            },
            "instructions": (
                "Mock interview for this specific role. Use STAR stories from profile only. "
                "Map likely questions to JD keywords."
            ),
        }
