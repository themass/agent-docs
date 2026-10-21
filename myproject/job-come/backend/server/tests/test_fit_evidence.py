import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jc.domain.fit_evidence import verify_requirement_evidence
from jc.schemas.job import JDParseResult
from jc.schemas.profile_payload import ProfilePayload
from jc.services.fit_score_service import FitScoreService


def profile():
    return ProfilePayload.model_validate(
        {
            "experiences": [
                {
                    "id": "exp1",
                    "company": "甲",
                    "title": "开发",
                    "start_date": "2020",
                    "highlights": ["负责调度模块"],
                }
            ]
        }
    )


def jd():
    return JDParseResult(role_title="后端", must_have_skills=["调度系统", "团队管理"])


def test_citations_verified_by_exact_source_and_stable_entity_id():
    rows = verify_requirement_evidence(
        [
            {
                "requirement": "调度系统",
                "status": "supported",
                "importance": "required",
                "importance_basis": "jd_explicit",
                "evidence": [
                    {
                        "field_path": "experiences[0].highlights[0]",
                        "quote": "负责 调度模块",
                        "entity_id": "forged",
                    }
                ],
            }
        ],
        profile(),
        jd(),
    )
    assert len(rows) == 2
    assert rows[0].citation_status == "verified"
    assert rows[0].evidence[0].entity_id == "exp1"
    assert rows[1].status == "unverified" and rows[1].next_question


@pytest.mark.parametrize(
    "path,quote",
    [
        ("experiences[0].highlights[0]", "主导平台"),
        ("experiences[99].highlights[0]", "负责调度模块"),
        ("constraints.retracted_claims[0].claim", "负责调度模块"),
    ],
)
def test_forged_or_rejected_claims_cannot_be_used_as_verified_citations(path, quote):
    row = verify_requirement_evidence(
        [
            {
                "requirement": "调度系统",
                "status": "supported",
                "importance": "required",
                "evidence": [{"field_path": path, "quote": quote}],
            }
        ],
        profile(),
        jd(),
    )[0]
    assert row.status == "unverified" and row.evidence == []
    assert row.importance == "unspecified"  # estimated cannot become a hard requirement


def test_extra_requirements_are_not_added_by_model():
    assert (
        len(
            verify_requirement_evidence(
                [
                    {"requirement": "模型自己添加", "status": "supported"},
                ],
                profile(),
                jd(),
            )
        )
        == 2
    )


@pytest.mark.asyncio
async def test_production_score_sends_valid_complete_json_and_verifies_return(monkeypatch):
    from jc.services import fit_score_service as module

    monkeypatch.setattr(module.settings, "jc_llm_enabled", True)
    response = {
        "score": 60,
        "recommendation": "caution",
        "requirement_evidence": [
            {
                "requirement": "调度系统",
                "status": "supported",
                "evidence": [
                    {
                        "field_path": "experiences[0].highlights[0]",
                        "quote": "假的",
                    }
                ],
            }
        ],
    }

    async def complete(*args, **kwargs):
        data = json.loads(kwargs["messages"][1]["content"])
        assert "i18n" not in data["profile"] and "photo" not in data["profile"]["contact"]
        assert data["profile"]["experiences"][0]["highlights"] == ["负责调度模块"]
        return kwargs["response_validator"](response)

    router = SimpleNamespace(acompletion=complete, content_from_response=lambda r: json.dumps(r))
    monkeypatch.setattr(module, "get_llm_router", lambda: router)
    result = await FitScoreService().score(profile=profile(), jd=jd())
    assert result.requirement_evidence[0].status == "unverified"
    assert len(result.requirement_evidence) == 2


@pytest.mark.asyncio
async def test_over_budget_does_not_send_truncated_or_partial_json(monkeypatch):
    from jc.exceptions import AppError
    from jc.services import fit_score_service as module

    monkeypatch.setattr(module.settings, "jc_llm_enabled", True)
    router = SimpleNamespace(acompletion=AsyncMock())
    monkeypatch.setattr(module, "get_llm_router", lambda: router)
    payload = profile()
    payload.experiences[0].highlights = ["字" * 101000]
    with pytest.raises(AppError, match="处理上限"):
        await FitScoreService().score(profile=payload, jd=jd())
    router.acompletion.assert_not_awaited()


def test_denied_claim_still_in_old_source_cannot_be_positive_evidence():
    payload = profile()
    from jc.schemas.profile_payload import RetractedClaim

    payload.constraints.retracted_claims = [
        RetractedClaim(
            claim="负责调度模块",
            correction="只是参与测试",
            scope="experience",
            entity_id="exp1",
        )
    ]
    result = verify_requirement_evidence(
        [
            {
                "requirement": "调度系统",
                "status": "supported",
                "evidence": [
                    {
                        "field_path": "experiences[0].highlights[0]",
                        "quote": "负责调度模块",
                    }
                ],
            }
        ],
        payload,
        jd(),
    )
    assert result[0].status == "unverified" and not result[0].evidence
