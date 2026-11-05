"""How ready the candidate looks after a mock interview, as one of four tiers.

Computed here, by rules, never by the model: the same scores always give the same tier, and a
cap can only lower it. The reviewer writes the words around it. The tier says how the interview
went, not whether the candidate would be hired; the report says so too.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jc.coach.level import LEVEL_SPECS
from jc.coach.report_insights import DIMENSION_LABEL

#: (lower bound of the mean, tier), highest first. A mean on a bound is in the higher tier.
_TIERS: tuple[tuple[float, str], ...] = (
    (7.5, "solid"), (6.0, "ready"), (4.5, "targeted"), (0.0, "need_more"),
)
LABELS = {
    "need_more": "还需大量准备",
    "targeted": "需针对性补强",
    "ready": "基本可以上场",
    "solid": "表现稳定",
}
_ORDER = ("need_more", "targeted", "ready", "solid")
#: One dimension this low keeps the interview from reading as ready, however the others went.
_WEAK_DIMENSION = 3.0
#: At least this share of the job's must-haves has to have been asked about.
_MIN_COVERAGE = 0.5


def _lower(tier: str, cap: str) -> str:
    return _ORDER[min(_ORDER.index(tier), _ORDER.index(cap))]


def readiness(
    overall: Mapping[str, float | None],
    coverage: Mapping[str, int] | None,
    *,
    level: str | None,
    ended_early: bool,
) -> dict[str, Any] | None:
    """The tier, its label, the sentence for the page and the lines it rests on. None when no
    dimension was scored."""
    scored = {dim: value for dim, value in overall.items() if value is not None}
    if not scored:
        return None
    mean = round(sum(scored.values()) / len(scored), 1)
    tier = next(name for floor, name in _TIERS if mean >= floor)
    basis = [f"五维平均 {mean:.1f}"]

    # Each cap says what it saw. It adds "最多评到" only when it actually lowered the tier, so a
    # line never reads as the reason for a tier the scores had already put there.
    def cap(current: str, fact: str) -> str:
        lowered = _lower(current, "targeted")
        basis.append(f"{fact}，最多评到“{LABELS['targeted']}”" if lowered != current else fact)
        return lowered

    for dim in sorted(dim for dim, value in scored.items() if value <= _WEAK_DIMENSION):
        label = DIMENSION_LABEL.get(dim, dim)
        tier = cap(tier, f"{label}只有 {scored[dim]:g} 分")

    if coverage and coverage.get("total"):
        total, asked = int(coverage["total"]), int(coverage["asked"])
        if asked / total < _MIN_COVERAGE:
            tier = cap(tier, f"岗位必备项 {total} 项里只问到 {asked} 项")

    if ended_early:
        tier = cap(tier, "面试提前结束")

    spec = LEVEL_SPECS.get(level or "")
    statement = f"按{spec.label}的要求：{LABELS[tier]}" if spec else LABELS[tier]
    return {"tier": tier, "label": LABELS[tier], "statement": statement, "basis": basis}
