"""Fit LLM JSON → FitScoreResponse (elevate_hints always allowed)."""

from jobcome.services.fit_score_service import fit_response_from_llm


def test_fit_parses_elevate_hints_and_neutral_legitimacy() -> None:
    result = fit_response_from_llm(
        {
            "score": 42,
            "recommendation": "no",
            "gaps": ["缺少 K8s 实操"],
            "blockers": [],
            "summary": "匹配偏低，仍可按该岗改稿。",
            "elevate_hints": ["把已有容器化经历写进要点"],
            "dimensions": {"match": 40, "target": 55, "comp": 50, "culture": 60, "red_flags": 20},
            "legitimacy": "caution",
        }
    )
    assert result.recommendation == "no"
    assert result.elevate_hints == ["把已有容器化经历写进要点"]
    assert result.dimensions["match"] == 40
    assert result.legitimacy == "caution"


def test_fit_clamps_bad_recommendation() -> None:
    result = fit_response_from_llm({"score": 90, "recommendation": "maybe"})
    assert result.recommendation == "caution"
    assert result.elevate_hints == []
