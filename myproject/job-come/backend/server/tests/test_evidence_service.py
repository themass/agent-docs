"""Evidence service: join gaps to answers, and let only the user add facts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jc.schemas.evidence import EvidenceAnswerInput, EvidenceAnswerRequest
from jc.schemas.profile_payload import (
    EvidenceAnswer,
    ProfileExperience,
    ProfilePayload,
    ProfilePreferences,
)
from jc.services.evidence_service import EvidenceService


def _exp(*highlights: str, title: str = "后端工程师") -> ProfileExperience:
    return ProfileExperience(
        id="e1",
        company="某公司",
        title=title,
        start_date="2020-01",
        highlights=list(highlights),
    )


def _service(payload: ProfilePayload, *, profile_row=None) -> EvidenceService:
    service = object.__new__(EvidenceService)
    service._db = SimpleNamespace(commit=AsyncMock())
    service._profiles = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(id="prof_1", payload=payload, version=2))
    )
    service._store = SimpleNamespace(get_by_id=AsyncMock(return_value=profile_row))
    return service


@pytest.mark.asyncio
async def test_gaps_are_returned_with_the_family_catalogue() -> None:
    """The user must be able to override an inferred family, so the catalogue ships."""
    payload = ProfilePayload(experiences=[_exp("参与统一配置中心的建设与推广工作")])
    resp = await _service(payload).list_gaps("prof_1", actor=SimpleNamespace())

    assert resp.role_family == "backend"
    assert resp.gaps
    assert any(f["id"] == "backend" for f in resp.families)


@pytest.mark.asyncio
async def test_an_explicit_preference_beats_title_inference() -> None:
    payload = ProfilePayload(
        experiences=[_exp("参与统一配置中心的建设与推广工作")],
        preferences=ProfilePreferences(role_family="pm"),
    )
    resp = await _service(payload).list_gaps("prof_1", actor=SimpleNamespace())
    assert resp.role_family == "pm"


@pytest.mark.asyncio
async def test_answered_questions_are_not_asked_again() -> None:
    """Re-asking a question the user already answered makes the feature feel broken."""
    payload = ProfilePayload(experiences=[_exp("参与统一配置中心的建设与推广工作")])
    first = await _service(payload).list_gaps("prof_1", actor=SimpleNamespace())
    answered = first.gaps[0]

    payload.evidence_answers = [
        EvidenceAnswer(
            field_path=answered.field_path,
            question=answered.question,
            answer="我独立负责，覆盖 40 多个服务",
        )
    ]
    second = await _service(payload).list_gaps("prof_1", actor=SimpleNamespace())

    assert answered.question not in [g.question for g in second.gaps]
    assert second.answered_count == 1


@pytest.mark.asyncio
async def test_submitting_answers_appends_facts_and_bumps_version() -> None:
    payload = ProfilePayload(experiences=[_exp("参与统一配置中心的建设与推广工作")])
    row = SimpleNamespace(payload=payload.model_dump(mode="json"), version=2)
    service = _service(payload, profile_row=row)

    resp = await service.submit_answers(
        "prof_1",
        actor=SimpleNamespace(),
        body=EvidenceAnswerRequest(
            answers=[
                EvidenceAnswerInput(
                    field_path="experiences[0].highlights[0]",
                    question="你在这件事里承担到什么程度？",
                    answer="我独立负责，覆盖 40 多个服务",
                    kind="weak_ownership",
                )
            ],
        ),
    )

    stored = ProfilePayload.model_validate(row.payload)
    assert resp.stored == 1
    assert resp.version == 3
    assert stored.evidence_answers[0].answer == "我独立负责，覆盖 40 多个服务"
    # The user's own bullet must survive untouched: we add facts, never rewrite theirs.
    assert stored.experiences[0].highlights == ["参与统一配置中心的建设与推广工作"]


@pytest.mark.asyncio
async def test_resubmitting_the_same_question_updates_rather_than_duplicates() -> None:
    payload = ProfilePayload(
        experiences=[_exp("参与统一配置中心的建设与推广工作")],
        evidence_answers=[
            EvidenceAnswer(
                field_path="experiences[0].highlights[0]",
                question="你在这件事里承担到什么程度？",
                answer="旧答案",
            )
        ],
    )
    row = SimpleNamespace(payload=payload.model_dump(mode="json"), version=5)
    service = _service(payload, profile_row=row)

    await service.submit_answers(
        "prof_1",
        actor=SimpleNamespace(),
        body=EvidenceAnswerRequest(
            answers=[
                EvidenceAnswerInput(
                    field_path="experiences[0].highlights[0]",
                    question="你在这件事里承担到什么程度？",
                    answer="新答案",
                )
            ]
        ),
    )

    stored = ProfilePayload.model_validate(row.payload)
    assert len(stored.evidence_answers) == 1
    assert stored.evidence_answers[0].answer == "新答案"


@pytest.mark.asyncio
async def test_answering_never_writes_the_role_family() -> None:
    """Answering a question is not a statement about the target role.

    The panel used to echo the *inferred* family back here, which froze a guess into
    an explicit user choice. Writing options is the only writer now.
    """
    payload = ProfilePayload(experiences=[_exp("参与统一配置中心的建设与推广工作")])
    row = SimpleNamespace(payload=payload.model_dump(mode="json"), version=1)
    service = _service(payload, profile_row=row)

    resp = await service.submit_answers(
        "prof_1",
        actor=SimpleNamespace(),
        body=EvidenceAnswerRequest(
            answers=[
                EvidenceAnswerInput(
                    field_path="experiences[0].highlights[0]",
                    question="覆盖了多少服务？",
                    answer="40 多个",
                )
            ],
        ),
    )

    stored = ProfilePayload.model_validate(row.payload)
    assert resp.stored == 1
    assert stored.evidence_answers[0].answer == "40 多个"
    assert stored.preferences.role_family is None
    # Still resolved for the response so the client can refresh its question list.
    assert resp.role_family == "backend"


@pytest.mark.asyncio
async def test_blank_answers_are_dropped() -> None:
    payload = ProfilePayload(experiences=[_exp("参与统一配置中心的建设与推广工作")])
    row = SimpleNamespace(payload=payload.model_dump(mode="json"), version=1)
    service = _service(payload, profile_row=row)

    resp = await service.submit_answers(
        "prof_1",
        actor=SimpleNamespace(),
        body=EvidenceAnswerRequest(
            answers=[
                EvidenceAnswerInput(
                    field_path="experiences[0].highlights[0]",
                    question="覆盖了多少服务？",
                    answer="   ",
                )
            ]
        ),
    )

    stored = ProfilePayload.model_validate(row.payload)
    assert resp.stored == 0
    assert stored.evidence_answers == []


def test_excerpt_cuts_on_a_phrase_boundary_not_mid_word() -> None:
    """Shared with the frontend's `lib/excerpt.ts`; both quote user text."""
    from jc.services.text_overlap import excerpt

    # Fits: returned unchanged, with no ellipsis implying something was removed.
    assert excerpt("短要点", 24) == "短要点"

    long = "为了提升打车业务的 GMV，以及满足高质量用户增长的目标，重构了派单调度模型"
    out = excerpt(long, 24)
    assert out.endswith("…")
    assert len(out) <= 25
    # Cut at the comma, and the comma itself is not left dangling before the ellipsis.
    assert "，…" not in out

    # No punctuation inside the window: cut at the limit rather than return the whole
    # string, but still mark it as partial.
    dense = "一" * 40
    assert excerpt(dense, 10) == "一" * 10 + "…"
