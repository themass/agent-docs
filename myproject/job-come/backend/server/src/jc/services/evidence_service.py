"""Evidence-gap orchestration: ask for missing proof, store the user's answers.

Why this is a service and not just the scanner
----------------------------------------------
`evidence_gaps.find_evidence_gaps` is a pure function over a profile. Turning it into a
product feature needs three more things, and all three are trust-boundary decisions:

1. **Already-answered questions must not be asked again.** Answers live on the profile,
   so the gap list has to be joined against them before it reaches the user.
2. **The role family must be settleable by the user.** Inference from a job title is a
   guess, and guessing wrong means the whole document is written for the wrong reader.
   So the response ships the catalogue and the choice is persisted when made.
3. **Only the user may add facts.** Answers are written verbatim into
   `payload.evidence_answers` and nothing else on the profile is touched. No model is in
   this path, no existing bullet is rewritten, and `version` is bumped so a concurrent
   editor still gets its optimistic-lock conflict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agentkit.web.auth import Actor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.db.profile_snapshot_hook import bind_snapshot_source
from jc.domain.role_families import all_families, get_playbook, resolve_role_family
from jc.exceptions import NotFoundError
from jc.schemas.evidence import (
    EvidenceAnswerRequest,
    EvidenceAnswerResponse,
    EvidenceGapItem,
    EvidenceGapsResponse,
    MetricCandidateItem,
)
from jc.schemas.profile_payload import EvidenceAnswer, ProfilePayload
from jc.services.evidence_gaps import find_evidence_gaps
from jc.services.metric_prompts import candidates_for_kind
from jc.services.profile_service import ProfileService
from jc.stores.profile_store import ProfileStore


def _answer_key(field_path: str, question: str) -> str:
    return f"{field_path}::{question}"


class EvidenceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._profiles = ProfileService(db)
        self._store = ProfileStore(db)

    async def list_gaps(
        self,
        profile_id: str,
        *,
        actor: Actor,
        job_id: str | None = None,
        limit: int = 12,
    ) -> EvidenceGapsResponse:
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = profile_resp.payload

        job_category: str | None = None
        job_title: str | None = None
        if job_id:
            from jc.stores.job_store import JobStore

            job = await JobStore(self._db).get_by_id(job_id)
            if job is not None and job.profile_id == profile_id:
                job_category = job.role_category
                job_title = job.title

        family = resolve_role_family(
            override=payload.preferences.role_family,
            job_category=job_category,
            job_title=job_title,
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )
        playbook = get_playbook(family)

        answered = {
            _answer_key(a.field_path, a.question): a.answer
            for a in payload.evidence_answers
        }
        # Ask for more than we will show, because answered questions are filtered out
        # afterwards and a user who answered the top five should still see a next five.
        gaps = find_evidence_gaps(payload, role_family=family, limit=limit * 3)

        items: list[EvidenceGapItem] = []
        for gap in gaps:
            if _answer_key(gap.field_path, gap.question) in answered:
                continue
            items.append(
                EvidenceGapItem(
                    field_path=gap.field_path,
                    kind=gap.kind,
                    source_text=gap.source_text,
                    question=gap.question,
                    examples=list(gap.examples),
                    weight=gap.weight,
                    metrics=[
                        MetricCandidateItem(**c.to_dict())
                        for c in candidates_for_kind(playbook, gap.kind)
                    ],
                )
            )
            if len(items) >= limit:
                break

        return EvidenceGapsResponse(
            role_family=playbook.id,
            role_label=playbook.label,
            quantification_optional=playbook.quantification_optional,
            gaps=items,
            answered_count=len(answered),
            families=all_families(),
        )

    async def submit_answers(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: EvidenceAnswerRequest,
    ) -> EvidenceAnswerResponse:
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        profile = await self._store.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")

        payload = ProfilePayload.model_validate(profile.payload)
        existing: dict[str, EvidenceAnswer] = {
            _answer_key(a.field_path, a.question): a for a in payload.evidence_answers
        }

        now = datetime.now(UTC)
        stored = 0
        for incoming in body.answers:
            text = incoming.answer.strip()
            if not text:
                continue
            key = _answer_key(incoming.field_path, incoming.question)
            existing[key] = EvidenceAnswer(
                field_path=incoming.field_path,
                question=incoming.question,
                answer=text,
                kind=incoming.kind,
                answered_at=now,
            )
            stored += 1

        payload.evidence_answers = list(existing.values())

        # The role family is NOT written here. Answering an evidence question says nothing
        # about which family the user targets, and the client used to echo back the
        # *inferred* family -- which silently froze a guess into an explicit choice.
        # Writing options own that field; see TECH-API.md section 5.
        family = payload.preferences.role_family or resolve_role_family(
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )

        with bind_snapshot_source("evidence"):
            profile.payload = payload.model_dump(mode="json")
            profile.version += 1
            await self._db.commit()

        return EvidenceAnswerResponse(
            profile_id=profile_resp.id,
            version=profile.version,
            stored=stored,
            role_family=family,
        )

    @staticmethod
    def as_writer_context(payload: ProfilePayload) -> list[dict[str, Any]]:
        """User-supplied facts, formatted for the writer prompt."""
        return [
            {"field_path": a.field_path, "question": a.question, "answer": a.answer}
            for a in payload.evidence_answers
        ]
