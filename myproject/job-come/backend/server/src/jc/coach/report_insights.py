"""What a mock-interview report says beyond the scores: the weakest dimensions with a practice for
each, the first five against the last five questions, and how the JD's must-haves were reached.

Everything here is computed from the stored review and the session's questions, so it is derived,
never stored, and it cannot disagree with the scores on the page.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from jc.coach.coverage import coverage_of

DIMENSION_LABEL = {
    "structure": "结构",
    "relevance": "相关性",
    "depth": "深度",
    "communication": "表达",
    "reflection": "反思",
}

#: One concrete exercise per dimension, the same wording for every candidate.
PRACTICE = {
    "structure": "回答前先在心里排出情境、任务、行动、结果四段，每段一句，再展开。",
    "relevance": "先用一句话直接回答被问的问题，再举例，不要先讲背景。",
    "depth": "每个方案都说出一个取舍：替代方案是什么，代价在哪里。",
    "communication": "先说结论再说依据；术语第一次出现时用一句话解释。",
    "reflection": "说出一件你做得不够的事、你当时的判断，以及下次怎么验证改进。",
}

#: A question counts as having met a requirement when its mean score reaches this.
MEET_THRESHOLD = 6
SUGGESTION_COUNT = 3
TREND_SIZE = 5


def _mean(values: Sequence[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def question_mean(scores: dict[str, int | None]) -> float | None:
    return _mean([v for v in scores.values() if v is not None])


def insights(
    questions: list[dict[str, Any]],
    overall: dict[str, float | None],
    must_have: list[str],
    stems: dict[str, str],
) -> dict[str, Any]:
    """`questions` are the report's per-question entries in asked order; `stems` maps a question id
    to its text; `overall` holds the server's five-dimension averages."""
    # Trend: first five against last five, only when there are enough questions for both to differ.
    trend = None
    means = [question_mean(q["scores"]) for q in questions]
    scored = [m for m in means if m is not None]
    if len(questions) >= 2 * TREND_SIZE and len(scored) >= 2 * TREND_SIZE:
        trend = {
            "first_five": _mean(scored[:TREND_SIZE]),
            "last_five": _mean(scored[-TREND_SIZE:]),
        }

    # Coverage: which requirements were put to the candidate, and which of those were met.
    asked_stems = [stems.get(q["question_id"], "") for q in questions]
    asked = coverage_of(must_have, asked_stems)
    meet: set[str] = set()
    for q, mean in zip(questions, means):
        if mean is not None and mean >= MEET_THRESHOLD:
            meet.update(coverage_of(must_have, [stems.get(q["question_id"], "")]).covered)
    coverage = {"total": len(must_have), "asked": len(asked.covered), "meet": len(meet)}

    # Suggestions: the three weakest dimensions, each with one practice and the question where that
    # dimension scored lowest, so the candidate can go back to it in the bank.
    ranked = sorted(
        ((dim, value) for dim, value in overall.items() if value is not None and dim in PRACTICE),
        key=lambda item: item[1],
    )
    suggestions = []
    for dim, value in ranked[:SUGGESTION_COUNT]:
        scored_for_dim = [
            (q["scores"][dim], q["question_id"])
            for q in questions
            if q["scores"].get(dim) is not None
        ]
        lowest = min(scored_for_dim, key=lambda item: item[0])[1] if scored_for_dim else None
        suggestions.append({
            "dimension": dim,
            "label": DIMENSION_LABEL[dim],
            "average": value,
            "practice": PRACTICE[dim],
            "question_id": lowest,
        })
    return {"trend": trend, "coverage": coverage, "suggestions": suggestions}
