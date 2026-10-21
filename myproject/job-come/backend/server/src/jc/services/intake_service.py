"""Run the intake interview: read the plan, write the user's answers into the profile.

Why this writes structured fields when `EvidenceService` may not
----------------------------------------------------------------
`EvidenceService` only ever appends to `evidence_answers`, because it operates on a
profile the user has already reviewed and confirmed — silently editing confirmed content
is what the trust boundary forbids. Intake is the opposite situation: the profile is
empty or a skeleton, there is nothing to protect, and an interview that cannot write
`contact.name` can never produce a document at all.

So this service may write structured fields, under three constraints:

1. **Only the path the question named.** `target_path` comes from the plan, not from the
   client's imagination, and every write is matched against a fixed handler table. An
   unrecognised path falls back to append-only.
2. **Verbatim.** The user's text is stored as typed. Nothing is rewritten, normalised or
   summarised on the way in; turning answers into resume prose is the writer's job, at
   generation time, where the user can see and reject the result.
3. **Mirrored as evidence.** Every answer is also recorded as an `EvidenceAnswer` with
   `kind="intake:{question_id}"`. That serves two purposes: the writer already treats
   those as user-authored source facts, and the set of answered ids is what makes the
   interview resumable without storing conversation state anywhere.

The profile is left in `draft` status throughout. Intake collects material; the user
still confirms the result on the review step exactly as they do after a file upload.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor
from sqlalchemy.ext.asyncio import AsyncSession

from jc.db.profile_snapshot_hook import bind_snapshot_source
from jc.domain.role_families import resolve_role_family
from jc.exceptions import NotFoundError
from jc.schemas.intake import (
    IntakeAnsweredItem,
    IntakeAnswerInput,
    IntakeAnswerRequest,
    IntakeAnswerResponse,
    IntakeAppliedWrite,
    IntakePlanResponse,
    IntakeQuestionItem,
    IntakeSplitRequest,
    IntakeSplitResponse,
    IntakeSplitSegment,
    IntakeStageItem,
)
from jc.schemas.profile_payload import (
    EvidenceAnswer,
    ProfileExperience,
    ProfilePayload,
)
from jc.services.intake_dictation import split_dictation
from jc.services.profile_intake import (
    NEW_EXPERIENCE_PATH,
    IntakePlan,
    build_intake_plan,
    describe_path,
    highlight_slot_ids,
    parse_highlight_target,
)
from jc.services.profile_service import ProfileService
from jc.stores.profile_store import ProfileStore

#: Marks an evidence answer as having come from the interview. The question id is kept in
#: the suffix so `answered_ids` is recoverable from the profile alone — the interview has
#: no server-side session, which is what makes closing the tab harmless.
_INTAKE_KIND = "intake"

_INDEXED_RE = re.compile(r"^(?P<root>[a-z_]+)\[(?P<idx>\d+)\](?:\.(?P<rest>.+))?$")
_DATE_HINT_RE = re.compile(r"((?:19|20)\d{2}(?:[-./年]\d{1,2})?)")
_SPLIT_RE = re.compile(r"\s*[·|｜/、,，]\s*|\s{2,}")
_HIGHLIGHT_SLOT_RE = re.compile(r"^highlights\[(?P<slot>\d+)\]$")


def answered_question_ids(payload: ProfilePayload) -> frozenset[str]:
    """Which interview questions this profile has already answered.

    Public because the agent's `jc_intake_plan` tool needs the same answer as the
    panel. A separate derivation would be a plan that disagrees with itself: the panel
    would stop asking a question while the agent kept asking it.
    """
    out: set[str] = set()
    for answer in payload.evidence_answers:
        kind = (answer.kind or "").strip()
        if kind.startswith(f"{_INTAKE_KIND}:"):
            out.add(kind.split(":", 1)[1])
    return frozenset(out)


def _ensure_experience(payload: ProfilePayload, idx: int) -> ProfileExperience:
    """The experience at `idx`, creating empty ones up to it if needed.

    A plan can legitimately ask about `experiences[1]` before one exists — that is the
    "是否还有更早的经历" question. Creating the slot on write keeps the answer handlers
    from each needing to know whether they are filling or extending.
    """
    while len(payload.experiences) <= idx:
        payload.experiences.append(
            ProfileExperience(
                id=new_id("exp"),
                company="",
                title="",
                start_date="",
            )
        )
    return payload.experiences[idx]


def _parse_role_identity(text: str) -> tuple[str, str, str, str | None]:
    """Split "公司 · 职位 · 2021-03 至今" into its parts, best effort.

    Deliberately a heuristic and deliberately lossy-safe: whatever cannot be identified
    stays in `title`, which the user sees and corrects on the review step. The
    alternative — asking three separate questions for one fact the user would type in one
    breath — makes the interview feel like a form, which is the thing it exists to avoid.
    """
    body = text.strip()
    dates: list[str] = _DATE_HINT_RE.findall(body)
    start = dates[0] if dates else ""
    end: str | None = dates[1] if len(dates) > 1 else None
    if any(token in body for token in ("至今", "现在", "present", "Present", "now")):
        end = None

    # Remove the date fragment so it does not end up inside the company or title.
    without_dates = body
    for token in dates:
        without_dates = without_dates.replace(token, " ")
    for token in ("至今", "现在", "present", "Present", "now", "—", "–", "~", "-"):
        without_dates = without_dates.replace(token, " ")

    parts = [p.strip() for p in _SPLIT_RE.split(without_dates) if p.strip()]
    company = parts[0] if parts else ""
    title = parts[1] if len(parts) > 1 else ""
    if not title and len(parts) == 1:
        # One blob: better to treat it as the company and leave the title blank than to
        # guess, because a wrong title changes which playbook the resume is written to.
        title = ""
    return company, title, start, end


def _apply_contact(payload: ProfilePayload, rest: str, text: str) -> str | None:
    if rest == "name":
        payload.contact.name = text
        return "contact.name"
    if rest in ("email", "phone"):
        # One question covers both; the shape of the answer decides where it lands.
        if "@" in text:
            payload.contact.email = text
        else:
            payload.contact.phone = text
        return "contact.email" if "@" in text else "contact.phone"
    if rest == "location":
        payload.contact.location = text
        return "contact.location"
    return None


def _apply_experience(payload: ProfilePayload, idx: int, rest: str | None, text: str) -> str | None:
    exp = _ensure_experience(payload, idx)
    if rest is None:
        company, title, start, end = _parse_role_identity(text)
        exp.company = company or exp.company or text
        exp.title = title or exp.title
        exp.start_date = start or exp.start_date
        exp.end_date = end if end is not None else exp.end_date
        return f"experiences[{idx}]"
    if rest == "scope":
        exp.scope = text
        return f"experiences[{idx}].scope"
    if rest.startswith("highlights"):
        # Write the slot the question named, instead of appending. The plan keys highlight
        # questions by absolute slot (`highlights[1]`), so an append would put a revised
        # answer in a *new* slot and leave the old text in place — the user would see
        # their correction added as an extra bullet rather than replacing the wrong one.
        slot_match = _HIGHLIGHT_SLOT_RE.match(rest)
        named = int(slot_match.group("slot")) if slot_match else len(exp.highlights)
        # Clamped rather than padded: a gap would have to be filled with empty strings,
        # and an empty highlight is a bullet-shaped hole in the rendered resume. The plan
        # never asks beyond the end, so this only guards a hand-built request.
        slot = min(named, len(exp.highlights))
        if slot == len(exp.highlights):
            exp.highlights.append(text)
        else:
            exp.highlights[slot] = text
        return f"experiences[{idx}].highlights[{slot}]"
    return None


def _apply_preferences(payload: ProfilePayload, rest: str, text: str) -> str | None:
    if rest == "target_roles":
        values = [p.strip() for p in _SPLIT_RE.split(text) if p.strip()]
        payload.preferences.target_roles = values or [text]
        return "preferences.target_roles"
    return None


def _insert_experience(payload: ProfilePayload, text: str) -> str:
    """Record a role as the new most-recent one, pushing the existing ones down.

    Only the stale-profile question uses this, and it is the one case where writing to
    `experiences[0]` would be wrong: that index already holds the job the user left, and
    overwriting it would delete a real role to make room for another. The resume reads
    "most recent first" off this order, so the insertion has to happen here rather than
    being left for the user to reorder in the editor afterwards.
    """
    company, title, start, end = _parse_role_identity(text)
    payload.experiences.insert(
        0,
        ProfileExperience(
            id=new_id("exp"),
            company=company or text,
            title=title,
            start_date=start,
            end_date=end,
        ),
    )
    return "experiences[0]"


def apply_answer(payload: ProfilePayload, target_path: str, text: str) -> str | None:
    """Write one answer to the path the plan named. Returns the path actually written."""
    path = (target_path or "").strip()
    if not path:
        return None

    if path == NEW_EXPERIENCE_PATH:
        return _insert_experience(payload, text)

    match = _INDEXED_RE.match(path)
    if match:
        root = match.group("root")
        idx = int(match.group("idx"))
        rest = match.group("rest")
        if root == "experiences":
            return _apply_experience(payload, idx, rest, text)
        return None

    root, _, rest = path.partition(".")
    if root == "contact" and rest:
        return _apply_contact(payload, rest, text)
    if root == "preferences" and rest:
        return _apply_preferences(payload, rest, text)
    if root == "summary":
        payload.summary = text
        return "summary"
    return None


def record_intake_answers(
    payload: ProfilePayload,
    answers: Sequence[IntakeAnswerInput],
) -> tuple[list[IntakeAppliedWrite], int]:
    """Write a batch of interview answers into `payload` in place.

    Module-level rather than a method because two callers need exactly this and must
    not drift: the intake panel's `POST /intake-answers`, and the agent's
    `jc_intake_record` tool. The dangerous half is not the structured write, it is the
    `evidence_answers` bookkeeping — an answer recorded under the wrong kind is an
    answer the plan never counts, so the interview keeps asking a question the user has
    already answered, silently. One implementation, one failure mode.

    Returns the writes that landed on structured fields, plus how many answers were
    stored. The caller owns the profile version bump and the commit, because the two
    callers hold the row differently.
    """
    now = datetime.now(UTC)
    applied: list[IntakeAppliedWrite] = []
    stored = 0

    # Intake answers are keyed by question id alone, so re-answering a question
    # replaces it instead of leaving both versions on the profile. Answers from the
    # evidence-gap flow are left exactly as they are: several of those legitimately
    # share a kind and a field path while asking different things, so collapsing them
    # by anything coarser than their full identity would discard user content.
    kept: list[EvidenceAnswer] = []
    incoming_kinds = {f"{_INTAKE_KIND}:{a.question_id}" for a in answers if a.answer.strip()}
    for prior in payload.evidence_answers:
        if (prior.kind or "").strip() in incoming_kinds:
            continue
        kept.append(prior)

    for incoming in answers:
        text = incoming.answer.strip()
        if not text:
            continue
        written = apply_answer(payload, incoming.target_path, text)
        if written:
            applied.append(
                IntakeAppliedWrite(
                    path=written,
                    label=describe_path(payload, written),
                    value=text,
                )
            )
        # Recorded whether or not a structured field took it: this is both the
        # resumption state and the writer's source material.
        kept.append(
            EvidenceAnswer(
                field_path=written or incoming.target_path,
                question=incoming.question,
                answer=text,
                kind=f"{_INTAKE_KIND}:{incoming.question_id}",
                answered_at=now,
            )
        )
        stored += 1

    payload.evidence_answers = kept
    return applied, stored


def _plan_response(plan: IntakePlan, *, version: int) -> IntakePlanResponse:
    return IntakePlanResponse(
        mode=plan.mode,
        role_family=plan.role_family,
        role_label=plan.role_label,
        questions=[IntakeQuestionItem(**q.to_dict()) for q in plan.questions],
        answered=[IntakeAnsweredItem(**a.to_dict()) for a in plan.answered],
        stages=[IntakeStageItem(**s.to_dict()) for s in plan.stages],
        answered_count=plan.answered_count,
        can_generate=plan.can_generate,
        blocking=list(plan.blocking),
        version=version,
    )


class IntakeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._profiles = ProfileService(db)
        self._store = ProfileStore(db)

    async def get_plan(
        self,
        profile_id: str,
        *,
        actor: Actor,
        limit: int = 6,
    ) -> IntakePlanResponse:
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = profile_resp.payload
        family = resolve_role_family(
            override=payload.preferences.role_family,
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )
        plan = build_intake_plan(
            payload,
            role_family=family,
            answered_ids=answered_question_ids(payload),
            limit=limit,
        )
        return _plan_response(plan, version=profile_resp.version)

    async def split_answer(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: IntakeSplitRequest,
    ) -> IntakeSplitResponse:
        """Preview how one dictated answer breaks into separate bullets.

        Read-only. The split is shown, edited and only then submitted through
        `submit_answers`, because the boundary between two points is a judgement the
        punctuation can get wrong — and a profile write the user did not see is the one
        thing intake does not do.

        Only achievement answers fan out. Every other question names a single field: a
        name, a contact, a company line. Splitting those would produce segments with
        nowhere to go, so they come back as one segment and the UI shows nothing.
        """
        profile_resp = await self._profiles.get(profile_id, actor=actor)
        payload = profile_resp.payload
        segments = split_dictation(body.answer)
        target = parse_highlight_target(body.target_path)

        if target is None or len(segments) <= 1:
            text = segments[0] if segments else body.answer.strip()
            return IntakeSplitResponse(
                question_id=body.question_id,
                segments=[
                    IntakeSplitSegment(
                        question_id=body.question_id,
                        text=text,
                        target_path=body.target_path,
                        label=describe_path(payload, body.target_path),
                    )
                ],
                split=False,
            )

        idx, first_slot = target
        out: list[IntakeSplitSegment] = []
        for offset, text in enumerate(segments):
            # Consecutive slots from the one the question named. The question is always
            # for the first unfilled slot, so the following slots are free by
            # construction and no existing bullet can be displaced.
            question_id, path = highlight_slot_ids(idx, first_slot + offset)
            out.append(
                IntakeSplitSegment(
                    question_id=question_id,
                    text=text,
                    target_path=path,
                    label=describe_path(payload, path),
                )
            )
        return IntakeSplitResponse(question_id=body.question_id, segments=out, split=True)

    async def submit_answers(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: IntakeAnswerRequest,
    ) -> IntakeAnswerResponse:
        await self._profiles.get(profile_id, actor=actor)
        profile = await self._store.get_by_id(profile_id)
        if profile is None:
            raise NotFoundError("档案不存在或已删除。", code="profile_not_found")

        payload = ProfilePayload.model_validate(profile.payload or {})
        applied, stored = record_intake_answers(payload, body.answers)
        with bind_snapshot_source("intake"):
            profile.payload = payload.model_dump(mode="json")
            profile.version += 1
            await self._db.commit()

        family = resolve_role_family(
            override=payload.preferences.role_family,
            profile_titles=tuple(e.title for e in payload.experiences[:2]),
        )
        plan = build_intake_plan(
            payload,
            role_family=family,
            answered_ids=answered_question_ids(payload),
        )
        return IntakeAnswerResponse(
            profile_id=profile_id,
            version=profile.version,
            stored=stored,
            applied_paths=[w.path for w in applied],
            applied=applied,
            plan=_plan_response(plan, version=profile.version),
        )
