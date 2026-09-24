"""Pass/fail rules for one shadowing attempt."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from alignment import AlignmentScore, WordIssue

# MVP: closed set; expand with spaCy later if needed.
FUNCTION_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "and",
        "or",
        "but",
        "as",
        "by",
        "if",
        "so",
        "up",
        "is",
        "am",
        "are",
        "was",
        "were",
        "be",
        "been",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "my",
        "your",
        "his",
        "her",
        "its",
        "our",
        "their",
        "this",
        "that",
        "these",
        "those",
        "can",
        "could",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "please",
        "hi",
        "hello",
        "oh",
        "um",
        "uh",
    }
)

PassGrade = Literal["excellent", "pass", "retry"]


@dataclass(frozen=True)
class PassVerdict:
    """Structured pass result for UI and analytics."""

    pass_: bool
    grade: PassGrade
    reason: str


def is_content_word(word: str) -> bool:
    """Return True if word should block pass when missing or wrong."""
    normalized = word.lower().strip("'-")
    if not normalized:
        return False
    return normalized not in FUNCTION_WORDS


def judge_pass(score: AlignmentScore) -> PassVerdict:
    """Decide pass grade from alignment score.

    Rules (v1):
    - **retry**: completeness < 0.70, overall < 0.65, any wrong content word,
      or any missing content word.
    - **pass**: overall >= 0.72, completeness >= 0.75, no wrong/missing content words.
      Function-word omissions (a/the/to) allowed.
    - **excellent**: pass + overall >= 0.90 + completeness >= 0.92 + no wrong words.

    Extra words alone never block pass if content is intact.
    """
    problems = [i for i in score.issues if i.type in {"missing", "wrong", "extra"}]
    missing_content = [i for i in problems if i.type == "missing" and is_content_word(i.word)]
    wrong_content = [i for i in problems if i.type == "wrong" and is_content_word(i.word)]
    wrong_any = [i for i in problems if i.type == "wrong"]

    if score.completeness < 0.70 or score.overall < 0.65:
        return PassVerdict(False, "retry", "completeness_or_overall_too_low")

    if wrong_content:
        return PassVerdict(False, "retry", "wrong_content_word")

    if missing_content:
        return PassVerdict(False, "retry", "missing_content_word")

    if score.overall < 0.72 or score.completeness < 0.75:
        return PassVerdict(False, "retry", "below_pass_threshold")

    excellent = (
        score.overall >= 0.90
        and score.completeness >= 0.92
        and not wrong_any
    )
    if excellent:
        return PassVerdict(True, "excellent", "clean_shadow")

    return PassVerdict(True, "pass", "acceptable_with_minor_issues")
