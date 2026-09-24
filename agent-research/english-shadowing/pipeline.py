"""One shadowing turn: align + pass rules + bilingual coach."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alignment import align
from coach import CoachMessage, coach
from pass_rules import PassVerdict, judge_pass


@dataclass(frozen=True)
class EvaluateResult:
    """API-shaped result for one evaluate call."""

    reference: str
    transcript: str
    score: dict[str, float]
    issues: list[dict[str, Any]]
    coach: dict[str, str]
    pass_: bool
    grade: str
    pass_reason: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pass"] = data.pop("pass_")
        return data


def evaluate(
    reference: str,
    transcript: str,
    *,
    locale: str = "zh-CN",
    use_llm: bool = True,
) -> EvaluateResult:
    """Run full evaluate pipeline for one sentence.

    Args:
        reference: Standard sentence text.
        transcript: User speech as text (from ASR or simulation).
        locale: UI locale; coach returns zh+en always, client picks display.
        use_llm: Whether to attempt LLM coach.

    Returns:
        EvaluateResult ready for JSON serialization.
    """
    _ = locale  # reserved for future ja/es coach templates
    score = align(reference, transcript)
    verdict: PassVerdict = judge_pass(score)
    coach_msg: CoachMessage = coach(reference, transcript, score, use_llm=use_llm)

    issues_out = [
        {
            "type": i.type,
            "word": i.word,
            "expected": i.expected,
            "spoken": i.spoken,
            "hint": i.hint,
        }
        for i in score.issues
        if i.type != "ok"
    ]

    return EvaluateResult(
        reference=reference,
        transcript=transcript,
        score={
            "overall": score.overall,
            "completeness": score.completeness,
            "accuracy": score.accuracy,
        },
        issues=issues_out,
        coach=coach_msg.to_dict(),
        pass_=verdict.pass_,
        grade=verdict.grade,
        pass_reason=verdict.reason,
    )
