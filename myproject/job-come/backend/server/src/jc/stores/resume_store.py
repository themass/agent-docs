"""Resume draft and export persistence."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jc.models.enums import ExportJobStatus
from jc.models.resume import ExportJob, ResumeDraft


class ResumeStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_draft(self, draft: ResumeDraft) -> ResumeDraft:
        self._db.add(draft)
        await self._db.flush()
        return draft

    async def get_latest_draft(
        self,
        profile_id: str,
        *,
        elevation_level: str,
        locale: str | None = None,
        job_id: str | None = None,
    ) -> ResumeDraft | None:
        stmt = select(ResumeDraft).where(
            ResumeDraft.profile_id == profile_id,
            ResumeDraft.elevation_level == elevation_level,
            # Generic and job-targeted documents must never share a cache slot.
            ResumeDraft.job_id == job_id,
        )
        if locale:
            stmt = stmt.where(ResumeDraft.locale == locale)
        stmt = stmt.order_by(ResumeDraft.created_at.desc()).limit(1)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_draft_by_id(self, draft_id: str) -> ResumeDraft | None:
        stmt = select(ResumeDraft).where(ResumeDraft.id == draft_id)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def create_export_job(self, job: ExportJob) -> ExportJob:
        self._db.add(job)
        await self._db.flush()
        return job

    async def get_export_job(self, job_id: str) -> ExportJob | None:
        stmt = select(ExportJob).where(ExportJob.id == job_id)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def mark_export_done(self, job: ExportJob, *, storage_key: str) -> ExportJob:
        from datetime import UTC, datetime

        job.status = ExportJobStatus.DONE
        job.storage_key = storage_key
        job.completed_at = datetime.now(UTC)
        job.error_message = None
        await self._db.flush()
        return job

    async def mark_export_failed(self, job: ExportJob, message: str) -> ExportJob:
        job.status = ExportJobStatus.FAILED
        job.error_message = message[:512]
        await self._db.flush()
        return job

    async def list_drafts_for_profiles(self, profile_ids: list[str], *, limit: int) -> list[ResumeDraft]:
        if not profile_ids:
            return []
        stmt = (
            select(ResumeDraft)
            .where(ResumeDraft.profile_id.in_(profile_ids))
            .options(selectinload(ResumeDraft.job))
            .order_by(ResumeDraft.created_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_exports_for_drafts(self, draft_ids: list[str]) -> list[ExportJob]:
        if not draft_ids:
            return []
        stmt = (
            select(ExportJob)
            .where(ExportJob.resume_draft_id.in_(draft_ids))
            .order_by(ExportJob.created_at.asc())
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_exports_for_draft(self, draft_id: str) -> list[ExportJob]:
        stmt = select(ExportJob).where(ExportJob.resume_draft_id == draft_id)
        return list((await self._db.execute(stmt)).scalars().all())

    async def delete_draft(self, draft: ResumeDraft) -> None:
        """Remove a draft and the export records that point at it. Stored files are the caller's job."""
        await self._db.execute(delete(ExportJob).where(ExportJob.resume_draft_id == draft.id))
        await self._db.delete(draft)
        await self._db.flush()
