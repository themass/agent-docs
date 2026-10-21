"""Job parse and fit score orchestration."""

from __future__ import annotations

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.db.session import release_db_connection
from jc.domain.role_families import infer_role_family
from jc.exceptions import AppError, NotFoundError
from jc.models.job import Job
from jc.schemas.job import FitScoreRequest, FitScoreResponse, JobParseRequest, JobResponse
from jc.services.application_service import ApplicationService
from jc.services.fit_score_service import FitScoreService
from jc.services.jd_parser_service import JdParserService
from jc.services.profile_service import ProfileService
from jc.stores.job_store import JobStore


class JobService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._jobs = JobStore(db)
        self._profiles = ProfileService(db)
        self._jd = JdParserService()
        self._fit = FitScoreService()
        self._applications = ApplicationService(db)

    async def parse_url(self, profile_id: str, *, actor: Actor, body) -> JobResponse:
        # Authorize before any outbound request. Metadata is server-produced only.
        await self._profiles.get(profile_id, actor=actor)
        from jc.services.jd_fetch_service import JdFetchService
        page = await JdFetchService().fetch(body.url, render=body.render)
        provenance = page.as_dict()
        provenance.pop("text")
        return await self.parse_jd(profile_id, actor=actor,
            body=JobParseRequest(raw_text=page.text, source_url=page.final_url, save=body.save),
            provenance=provenance)

    async def parse_jd(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: JobParseRequest,
        provenance: dict | None = None,
    ) -> JobResponse:
        await self._profiles.get(profile_id, actor=actor)
        await release_db_connection(self._db)
        parsed = await self._jd.parse(raw_text=body.raw_text)

        requirements = parsed.model_dump(mode="json")
        if provenance:
            requirements["_provenance"] = provenance
        job: Job | None = None
        if body.save:
            job = Job(
                id=new_id("job"),
                profile_id=profile_id,
                company=parsed.company or "待确认公司",
                title=parsed.role_title,
                source_url=body.source_url,
                raw_text=body.raw_text[:50_000],
                requirements=requirements,
                # Stored so resume writing and mock interviews read this job through the
                # same playbook instead of each re-guessing from the title string.
                role_category=infer_role_family(parsed.role_title),
            )
            await self._jobs.create(job)
            await self._db.commit()

        return self._to_response(job, parsed=parsed) if job else JobResponse(
            id="",
            profile_id=profile_id,
            company=parsed.company or "待确认公司",
            title=parsed.role_title,
            source_url=body.source_url,
            requirements=requirements,
            fit_score=None,
            fit_recommendation=None,
            fit_gaps=[],
            fit_blockers=[],
            parsed=parsed,
            provenance=provenance,
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
        job_id: str | None = None
        raw_text: str | None = None
        requirements: dict | None = None
        if body.job_id:
            job = await self._jobs.get_by_id(body.job_id)
            if job is None or job.profile_id != profile_id:
                raise NotFoundError("职位不存在或已删除。", code="job_not_found")
            job_id = job.id
            raw_text = job.raw_text
            requirements = dict(job.requirements or {})

        if job_id is None and not body.raw_jd:
            # Not a 404: nothing was looked up. A missing argument is a bad request, and
            #「请求的内容不存在」 would send the user hunting for a job that was never named.
            raise AppError("请先选择一个职位或粘贴 JD 原文。", code="invalid_request")

        # Snapshot what the models need, then end the read transaction: JD parse plus fit
        # scoring can run for minutes and a remote MySQL server drops the idle connection.
        await release_db_connection(self._db)

        if job_id is not None:
            from jc.schemas.job import JDParseResult

            jd = JDParseResult.model_validate(requirements or {})
            if not jd.role_title:
                jd = await self._jd.parse(raw_text=raw_text or "")
        else:
            jd = await self._jd.parse(raw_text=body.raw_jd)

        result = await self._fit.score(profile=profile, jd=jd)
        result = result.model_copy(update={"evidence_profile_version": profile_resp.version})
        if job_id is not None:
            # The pooled connection was released above, so the ORM row must be re-loaded.
            job = await self._jobs.get_by_id(job_id)
            if job is None or job.profile_id != profile_id:
                raise NotFoundError("职位不存在或已删除。", code="job_not_found")
            job.fit_score = result.score
            job.fit_recommendation = result.recommendation
            job.fit_gaps = result.gaps
            job.fit_blockers = result.blockers
            job.fit_report = {
                "evidence_profile_version": result.evidence_profile_version,
                "requirement_evidence": [item.model_dump() for item in result.requirement_evidence],
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
            provenance=(job.requirements or {}).get("_provenance"),
            fit_score=job.fit_score,
            fit_recommendation=job.fit_recommendation,
            fit_gaps=job.fit_gaps if isinstance(job.fit_gaps, list) else [],
            fit_blockers=job.fit_blockers if isinstance(job.fit_blockers, list) else [],
            parsed=parsed,
            evidence_profile_version=report.get("evidence_profile_version"),
            requirement_evidence=report.get("requirement_evidence") or [],
            fit_summary=report.get("summary"),
            elevate_hints=list(report.get("elevate_hints") or []),
            fit_dimensions=dict(report.get("dimensions") or {}),
            legitimacy=report.get("legitimacy"),
        )
