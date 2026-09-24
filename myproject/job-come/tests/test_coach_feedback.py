"""Coach feedback normalization tests."""

from __future__ import annotations

from jobcome.coach.feedback import normalize_coach_feedback, overall_from_dimensions


def test_normalize_valid_feedback() -> None:
    raw = {
        "score": 7,
        "dimensions": {
            "structure": 8,
            "relevance": 7,
            "depth": 6,
            "communication": 8,
            "reflection": 6,
        },
        "strengths": ["clear STAR"],
        "gaps": ["needs metrics"],
    }
    out = normalize_coach_feedback(raw)
    assert out["score"] == 7
    assert out["dimensions"]["structure"] == 8


def test_overall_from_dimensions() -> None:
    dims = {"structure": 8, "relevance": 6, "depth": 7, "communication": 8, "reflection": 7}
    assert overall_from_dimensions(dims) == 7
