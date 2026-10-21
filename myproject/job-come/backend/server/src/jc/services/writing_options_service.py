"""Read and set the user's writing preferences for a profile.

Separate from `EvidenceService` because the two solve opposite problems. Evidence answers
are **new facts** and may only ever be appended, verbatim, by the user. Writing options
are **presentation choices** — which audience to write for, which supported fact to lead
with — and carry no factual risk at all, which is why this endpoint may simply set them.

This is the **only** writer of `payload.preferences.role_family`. The evidence endpoint
used to accept it too, and the panel echoed back the *inferred* family — which quietly
promoted a guess to an explicit user choice the moment anyone answered a question.
"""

from __future__ import annotations

from agentkit.web.auth import Actor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.db.profile_snapshot_hook import bind_snapshot_source
from jc.domain.role_families import PLAYBOOKS, all_families, get_playbook, resolve_role_family
from jc.exceptions import NotFoundError
from jc.schemas.profile_payload import ProfilePayload
from jc.schemas.writing_options import (
    FramingPresetOption,
    RoleFamilyOption,
    WritingOptionsRequest,
    WritingOptionsResponse,
)
from jc.services.framing_presets import MAX_EMPHASES, catalogue, resolve_emphases
from jc.services.profile_service import ProfileService
from jc.stores.profile_store import ProfileStore


class WritingOptionsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._profiles = ProfileService(db)
        self._store = ProfileStore(db)

    async def get(
        self,
        profile_id: str,
        *,
        actor: Actor,
        job_id: str | None = None,
    ) -> WritingOptionsResponse:
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = profile_resp.payload
        job_category, job_title = await self._job_context(profile_id, job_id)
        return self._compose(payload, job_category=job_category, job_title=job_title)

    async def update(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: WritingOptionsRequest,
        job_id: str | None = None,
    ) -> WritingOptionsResponse:
        await self._profiles.get(profile_id, actor=actor)
        profile = await self._store.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")
        payload = ProfilePayload.model_validate(profile.payload)

        if body.role_family is not None:
            requested = body.role_family.strip().lower()
            if not requested:
                # Explicitly clearing hands the decision back to inference, which is a
                # legitimate thing to want after changing target jobs.
                payload.preferences.role_family = None
            elif requested in PLAYBOOKS:
                payload.preferences.role_family = requested
            # An unknown id is ignored rather than rejected: a stale client must not be
            # able to fail the whole request over one bad dropdown value.

        if body.framing_emphases is not None:
            kept: list[str] = []
            known = {p["id"] for p in catalogue()}
            for raw in body.framing_emphases:
                pid = str(raw).strip().lower()
                if pid in known and pid not in kept:
                    kept.append(pid)
            # Store only what the user chose, capped. An empty list is meaningful: it
            # means "go back to the role default", which `resolve_emphases` supplies.
            payload.preferences.framing_emphases = kept[:MAX_EMPHASES]

        with bind_snapshot_source("writing_options"):
            profile.payload = payload.model_dump(mode="json")
            profile.version += 1
            await self._db.commit()

        job_category, job_title = await self._job_context(profile_id, job_id)
        return self._compose(payload, job_category=job_category, job_title=job_title)

    async def _job_context(
        self, profile_id: str, job_id: str | None
    ) -> tuple[str | None, str | None]:
        if not job_id:
            return None, None
        from jc.stores.job_store import JobStore

        job = await JobStore(self._db).get_by_id(job_id)
        if job is None or job.profile_id != profile_id:
            return None, None
        return job.role_category, job.title

    @staticmethod
    def _compose(
        payload: ProfilePayload,
        *,
        job_category: str | None,
        job_title: str | None,
    ) -> WritingOptionsResponse:
        override = payload.preferences.role_family
        family = resolve_role_family(
            override=override,
            job_category=job_category,
            job_title=job_title,
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )
        playbook = get_playbook(family)
        chosen = payload.preferences.framing_emphases
        emphases = resolve_emphases(chosen, role_family=playbook.id)
        return WritingOptionsResponse(
            role_family=playbook.id,
            role_label=playbook.label,
            role_family_explicit=bool(override),
            quantification_optional=playbook.quantification_optional,
            framing_emphases=emphases,
            framing_explicit=bool(chosen),
            max_emphases=MAX_EMPHASES,
            families=[RoleFamilyOption(**f) for f in all_families()],
            presets=[FramingPresetOption(**p) for p in catalogue(playbook.id)],
        )
