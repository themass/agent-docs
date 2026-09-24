"""Campaign progress and fit calibration."""

from __future__ import annotations

from datetime import UTC, date, datetime

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.enums import CampaignPhase, MockSessionStatus
from jobcome.models.interview import InterviewRecord, MockSession
from jobcome.models.job import Campaign, Job
from jobcome.schemas.job import CampaignStatsResponse
from jobcome.services.profile_service import ProfileService
from jobcome.stores.campaign_store import CampaignStore


class CampaignService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._campaigns = CampaignStore(db)
        self._profiles = ProfileService(db)

    async def get_stats(self, profile_id: str, *, actor: Actor) -> CampaignStatsResponse:
        await self._profiles.get(profile_id, actor=actor)
        campaign = await self._campaigns.get_for_profile(profile_id)
        if campaign is None:
            campaign = Campaign(
                id=new_id("camp"),
                profile_id=profile_id,
                phase=CampaignPhase.WARMUP,
                warmup_job_ids=[],
                target_job_ids=[],
                progress={},
            )
            await self._campaigns.create(campaign)
            await self._db.commit()

        interview_count = await self._count_interviews(profile_id)
        mock_count = await self._count_mock_sessions(profile_id)
        bank_count = await InterviewStore(self._db).count_questions(profile_id)
        calibration = await self._fit_calibration(profile_id)

        progress = dict(campaign.progress or {})
        progress.update(
            {
                "real_interviews": interview_count,
                "mock_sessions": mock_count,
                "bank_question_count": bank_count,
            }
        )
        campaign.progress = progress

        if (
            campaign.phase == CampaignPhase.WARMUP
            and interview_count >= 3
            and mock_count >= 5
        ):
            campaign.phase = CampaignPhase.TARGET
            campaign.target_unlocked_at = datetime.now(UTC)

        await self._campaigns.save(campaign)
        await self._db.commit()

        return CampaignStatsResponse(
            profile_id=profile_id,
            phase=campaign.phase,
            warmup_job_ids=list(campaign.warmup_job_ids or []),
            target_job_ids=list(campaign.target_job_ids or []),
            progress=progress,
            fit_calibration=calibration,
        )

    async def _count_interviews(self, profile_id: str) -> int:
        stmt = select(func.count()).select_from(InterviewRecord).where(
            InterviewRecord.profile_id == profile_id
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def _count_mock_sessions(self, profile_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(MockSession)
            .where(
                MockSession.profile_id == profile_id,
                MockSession.status != MockSessionStatus.CANCELLED,
            )
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def _fit_calibration(self, profile_id: str) -> dict:
        """Phase 4: which fit bands led to interviews (outcome → calibrate)."""
        stmt = select(Job).where(Job.profile_id == profile_id, Job.fit_score.is_not(None))
        jobs = list((await self._db.execute(stmt)).scalars().all())
        if not jobs:
            return {"sample_size": 0, "bands": {}}

        intr_stmt = select(InterviewRecord.job_id).where(
            InterviewRecord.profile_id == profile_id,
            InterviewRecord.job_id.is_not(None),
        )
        interviewed_job_ids = {row[0] for row in (await self._db.execute(intr_stmt)).all()}

        bands: dict[str, dict[str, int]] = {
            "go": {"total": 0, "interviewed": 0},
            "caution": {"total": 0, "interviewed": 0},
            "no": {"total": 0, "interviewed": 0},
        }
        for job in jobs:
            rec = job.fit_recommendation or "caution"
            if rec not in bands:
                rec = "caution"
            bands[rec]["total"] += 1
            if job.id in interviewed_job_ids:
                bands[rec]["interviewed"] += 1

        return {"sample_size": len(jobs), "bands": bands}

    async def tag_job(
        self,
        profile_id: str,
        job_id: str,
        *,
        actor: Actor,
        tag: str,
    ) -> CampaignStatsResponse:
        await self._profiles.get(profile_id, actor=actor)
        campaign = await self._campaigns.get_for_profile(profile_id)
        if campaign is None:
            campaign = Campaign(
                id=new_id("camp"),
                profile_id=profile_id,
                phase=CampaignPhase.WARMUP,
                warmup_job_ids=[],
                target_job_ids=[],
                progress={},
            )
            await self._campaigns.create(campaign)

        if tag == "target":
            ids = list(campaign.target_job_ids or [])
            if job_id not in ids:
                ids.append(job_id)
            campaign.target_job_ids = ids
        else:
            ids = list(campaign.warmup_job_ids or [])
            if job_id not in ids:
                ids.append(job_id)
            campaign.warmup_job_ids = ids

        await self._campaigns.save(campaign)
        await self._db.commit()
        return await self.get_stats(profile_id, actor=actor)
