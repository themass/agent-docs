import pytest
from pydantic import ValidationError

from jc.domain.claim_constraints import retracted_claim_findings
from jc.schemas.profile_payload import ProfilePayload
from jc.services.profile_patch_ops import apply_profile_patch
from jc.services.resume_service import ResumeService


def source():
    return ProfilePayload.model_validate(
        {
            "experiences": [
                {"id": eid, "company": eid, "title": "开发", "start_date": "2020"}
                for eid in ["e1", "e2"]
            ],
            "constraints": {
                "retracted_claims": [
                    {
                        "claim": "主导整个平台",
                        "correction": "负责调度模块",
                        "scope": "experience",
                        "entity_id": "e1",
                    }
                ]
            },
        }
    )


def test_scoped_rule_uses_stable_id_not_position_or_other_role():
    sections = {
        "experience_blocks": [
            {"id": "e2", "bullets": ["主导整个平台"]},
            {"id": "e1", "bullets": ["主导 整个平台"]},
            {"bullets": ["主导整个平台"]},
        ]
    }
    findings = retracted_claim_findings(sections, source())
    assert len(findings) == 1 and findings[0]["field"] == "experience_blocks[1].bullets[0]"


def test_corrected_text_and_unrelated_roles_are_not_rejected():
    assert (
        retracted_claim_findings(
            {
                "experience_blocks": [
                    {"id": "e1", "bullets": ["负责调度模块"]},
                    {"id": "e2", "bullets": ["主导整个平台"]},
                ]
            },
            source(),
        )
        == []
    )


def test_global_rules_cover_both_tracks_and_summary():
    payload = source().model_dump()
    payload["constraints"]["retracted_claims"][0].update(scope="profile", entity_id=None)
    sections = {
        "track": "bilingual",
        "zh_sections": {"summary": "主导整个平台"},
        "en_sections": {"summary": "主导整个平台"},
    }
    assert {
        item["field"]
        for item in retracted_claim_findings(sections, ProfilePayload.model_validate(payload))
    } == {
        "zh_sections.summary",
        "en_sections.summary",
    }


@pytest.mark.parametrize(
    "rule",
    [
        {"claim": "说法", "correction": "正确", "scope": "experience"},
        {"claim": "说法", "correction": "正确", "scope": "profile", "entity_id": "e1"},
        {"claim": "  ", "correction": "正确", "scope": "profile"},
    ],
)
def test_invalid_scope_is_not_silently_global(rule):
    with pytest.raises(ValidationError):
        ProfilePayload.model_validate({"constraints": {"retracted_claims": [rule]}})


def test_correction_can_be_confirmed_removed_and_survives_entity_reordering():
    before = source().model_dump()
    updated = apply_profile_patch(before, {"experiences": list(reversed(before["experiences"]))})
    assert updated.constraints.retracted_claims[0].entity_id == "e1"
    cleared = apply_profile_patch(updated.model_dump(), {"constraints.retracted_claims": []})
    assert cleared.constraints.retracted_claims == []
    assert source().constraints.retracted_claims  # caller was not mutated


def test_new_rule_must_point_to_real_entity():
    from jc.exceptions import AppError

    with pytest.raises(AppError):
        apply_profile_patch(
            source().model_dump(),
            {
                "constraints.retracted_claims": [
                    {
                        "claim": "说法",
                        "correction": "正确",
                        "scope": "experience",
                        "entity_id": "typo",
                    }
                ]
            },
        )


def test_production_quality_path_reports_recurrence_even_if_llm_passes():
    # No model invocation; verify actual production merge rather than prompt wording.
    sections = {"experience_blocks": [{"id": "e1", "bullets": ["主导整个平台"]}]}
    findings = ResumeService._with_invariant_issues([], sections, source().model_dump())
    assert any(
        item["code"] == "retracted_claim" and item["severity"] == "warning" for item in findings
    )
