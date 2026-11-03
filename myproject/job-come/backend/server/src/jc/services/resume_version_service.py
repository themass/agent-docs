"""List, view and delete a user's resume versions, grouped by profile."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentkit.web.auth import UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import NotFoundError
from jc.models.enums import ExportJobStatus
from jc.models.resume import ExportJob, ResumeDraft
from jc.services.profile_service import ProfileService
from jc.services.resume_render_engine import ResumeRenderEngine
from jc.stores.resume_store import ResumeStore
from jc.storage_backend import get_storage_backend
from jc.storage_client import download_url_for_key

logger = logging.getLogger(__name__)

# A user with many profiles and years of versions still gets one bounded page.
MAX_VERSIONS = 300


class ResumeVersionService:
    def __init__(self, db: AsyncSession, profiles: ProfileService) -> None:
        self._db = db
        self._profiles = profiles
        self._store = ResumeStore(db)

    async def list_grouped(self, *, actor: UserActor) -> dict[str, Any]:
        listing = await self._profiles.list_profiles(actor=actor)
        profiles = listing["profiles"]
        drafts = await self._store.list_drafts_for_profiles(
            [p["id"] for p in profiles], limit=MAX_VERSIONS
        )
        exports = await self._store.list_exports_for_drafts([d.id for d in drafts])
        exports_by_draft: dict[str, list[ExportJob]] = {}
        for job in exports:
            exports_by_draft.setdefault(job.resume_draft_id or "", []).append(job)

        versions_by_profile: dict[str, list[dict[str, Any]]] = {}
        for draft in drafts:
            versions_by_profile.setdefault(draft.profile_id, []).append(
                self._version_item(draft, exports_by_draft.get(draft.id, []))
            )

        return {
            "groups": [
                {
                    "profile_id": p["id"],
                    "contact_name": p.get("contact_name"),
                    "is_active": p["id"] == listing["active_profile_id"],
                    "versions": versions_by_profile.get(p["id"], []),
                }
                for p in profiles
            ]
        }

    async def render_html(self, draft_id: str, *, actor: UserActor) -> str:
        draft = await self._owned_draft(draft_id, actor=actor)
        return ResumeRenderEngine().render_html(draft.sections, template_id=draft.template_id)

    async def delete(self, draft_id: str, *, actor: UserActor) -> None:
        draft = await self._owned_draft(draft_id, actor=actor)
        exports = await self._store.list_exports_for_draft(draft.id)
        # Files first, then rows: if a file cannot be removed the version stays listed, so the
        # user can retry, rather than disappearing while its resume text is still stored.
        backend = get_storage_backend()
        for job in exports:
            if job.storage_key:
                try:
                    await asyncio.to_thread(backend.delete_object, job.storage_key)
                except Exception:
                    logger.exception("could not delete stored export %s", job.storage_key)
                    raise
        await self._store.delete_draft(draft)
        await self._db.commit()

    async def _owned_draft(self, draft_id: str, *, actor: UserActor) -> ResumeDraft:
        draft = await self._store.get_draft_by_id(draft_id)
        if draft is None:
            raise NotFoundError("没找到这个版本，可能已经删除。", code="resume_version_not_found")
        # Raises when the profile is not the caller's; a version is never reached any other way.
        await self._profiles.get(draft.profile_id, actor=actor)
        return draft

    @staticmethod
    def _version_item(draft: ResumeDraft, exports: list[ExportJob]) -> dict[str, Any]:
        job = draft.job
        return {
            "id": draft.id,
            "created_at": draft.created_at,
            "job": {"id": job.id, "title": job.title, "company": job.company} if job else None,
            "elevation_level": draft.elevation_level,
            "locale": draft.locale,
            "template_id": draft.template_id,
            "reviewer_status": draft.reviewer_status,
            "exports": [
                {
                    "id": e.id,
                    "format": e.format,
                    "status": e.status,
                    "completed_at": e.completed_at,
                    "error_message": e.error_message,
                    "download_url": (
                        download_url_for_key(e.storage_key)
                        if e.status == ExportJobStatus.DONE and e.storage_key else None
                    ),
                }
                for e in exports
            ],
        }

