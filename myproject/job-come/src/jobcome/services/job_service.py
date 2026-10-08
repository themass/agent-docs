"""Job parse and fit score orchestration."""

from __future__ import annotations

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.exceptions import NotFoundError
from jobcome.models.job import Job
from jobcome.schemas.job import FitScoreRequest, FitScoreResponse, JobParseRequest, JobResponse
from jobcome.services.application_service import ApplicationService
from jobcome.services.fit_score_service import FitScoreService
from jobcome.services.jd_parser_service import JdParserService
from jobcome.services.profile_service import ProfileService
from jobcome.stores.job_store import JobStore


class JobService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._jobs = JobStore(db)
        self._profiles = ProfileService(db)
        self._jd = JdParserService()
        self._fit = FitScoreService()
        self._applications = ApplicationService(db)

    async def parse_jd(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: JobParseRequest,
    ) -> JobResponse:
        await self._profiles.get(profile_id, actor=actor)
        parsed = await self._jd.parse(raw_text=body.raw_text)

        job: Job | None = None
        if body.save:
            job = Job(
                id=new_id("job"),
                profile_id=profile_id,
                company=parsed.company or "待确认公司",
                title=parsed.role_title,
                source_url=body.source_url,
                raw_text=body.raw_text[:50_000],
                requirements=parsed.model_dump(mode="json"),
            )
            await self._jobs.create(job)
            await self._db.commit()

        return self._to_response(job, parsed=parsed) if job else JobResponse(
            id="",
            profile_id=profile_id,
            company=parsed.company or "待确认公司",
            title=parsed.role_title,
            source_url=body.source_url,
            requirements=parsed.model_dump(mode="json"),
            fit_score=None,
            fit_recommendation=None,
            fit_gaps=[],
            fit_blockers=[],
            parsed=parsed,
        )

    async def fit_score(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: FitScoreRequest,
    ) -> FitScoreResponse:
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        profile = profile_resp.payload

        job: Job | None = None
        if body.job_id:
            job = await self._jobs.get_by_id(body.job_id)
            if job is None or job.profile_id != profile_id:
                raise NotFoundError("Job not found")

        if job is not None:
            from jobcome.schemas.job import JDParseResult

            jd = JDParseResult.model_validate(job.requirements or {})
            if not jd.role_title:
                jd = await self._jd.parse(raw_text=job.raw_text)
        elif body.raw_jd:
            jd = await self._jd.parse(raw_text=body.raw_jd)
        else:
            raise NotFoundError("Provide job_id or raw_jd")

        result = await self._fit.score(profile=profile, jd=jd)
        if job is not None:
            job.fit_score = result.score
            job.fit_recommendation = result.recommendation
            job.fit_gaps = result.gaps
            job.fit_blockers = result.blockers
            job.fit_report = {
                "summary": result.summary,
                "elevate_hints": result.elevate_hints,
                "dimensions": result.dimensions,
                "legitimacy": result.legitimacy,
            }
            await self._jobs.save(job)
            if isinstance(actor, UserActor):
                await self._applications.upsert_evaluated(profile_id, job.id, actor=actor)
            await self._db.commit()
            result = result.model_copy(update={"job_id": job.id})
        return result

    async def list_jobs(self, profile_id: str, *, actor: Actor) -> list[JobResponse]:
        await self._profiles.get(profile_id, actor=actor)
        rows = await self._jobs.list_for_profile(profile_id)
        return [self._to_response(j) for j in rows]

    @staticmethod
    def _to_response(job: Job, *, parsed=None) -> JobResponse:
        report = job.fit_report if isinstance(job.fit_report, dict) else {}
        return JobResponse(
            id=job.id,
            profile_id=job.profile_id,
            company=job.company,
            title=job.title,
            source_url=job.source_url,
            requirements=job.requirements,
            fit_score=job.fit_score,
            fit_recommendation=job.fit_recommendation,
            fit_gaps=job.fit_gaps if isinstance(job.fit_gaps, list) else [],
            fit_blockers=job.fit_blockers if isinstance(job.fit_blockers, list) else [],
            parsed=parsed,
            fit_summary=report.get("summary"),
            elevate_hints=list(report.get("elevate_hints") or []),
            fit_dimensions=dict(report.get("dimensions") or {}),
            legitimacy=report.get("legitimacy"),
        )
