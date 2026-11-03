"""JD coverage for a full mock interview: every must-have requirement should be asked about.

Matching is deterministic on purpose. A question covers a requirement when they share its key term
(case-insensitive, whole token). The model writes the questions; this module decides whether the
set of questions reaches every must-have, so a plan can be checked without a model call.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# Words that carry no signal about a skill and would match almost any question.
_STOPWORDS = frozenset(
    {
        "熟悉",
        "了解",
        "掌握",
        "具备",
        "有",
        "的",
        "和",
        "与",
        "及",
        "经验",
        "能力",
        "良好",
        "的和",
        "好的",
        "作能",
        "与协",
        "的沟",
        "通与",
        "责任",
        "优先",
        "以上",
        "相关",
        "工作",
        "能够",
        "the",
        "and",
        "with",
        "experience",
        "knowledge",
        "of",
        "a",
        "an",
        "in",
        "to",
        "or",
    }
)
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9+#.]*")
_CJK_RUN = re.compile(r"[一-鿿]+")
# Chinese has no spaces, so a run like "了解微服务架构" is cut into the bigrams a question would
# actually use ("微服", "服务", "架构"), instead of being matched as one unbreakable word.
_CJK_GRAM = 2


def _cjk_grams(run: str) -> set[str]:
    if len(run) <= _CJK_GRAM:
        return {run}
    return {run[i : i + _CJK_GRAM] for i in range(len(run) - _CJK_GRAM + 1)}


def key_terms(requirement: str) -> set[str]:
    """Terms that identify a requirement: Latin words, and Chinese bigrams from each run."""
    terms: set[str] = set()
    for token in _LATIN.findall(requirement):
        normalised = token.lower().rstrip(".")
        if normalised not in _STOPWORDS and len(normalised) >= 2:
            terms.add(normalised)
    for run in _CJK_RUN.findall(requirement):
        if run in _STOPWORDS:
            continue
        terms |= {g for g in _cjk_grams(run) if g not in _STOPWORDS}
    return terms


@dataclass
class Coverage:
    total: int
    covered: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    #: True when there was nothing to cover. Reported as a gap, never as a pass.
    no_requirements: bool = False

    @property
    def complete(self) -> bool:
        return not self.no_requirements and not self.missing

    @property
    def ratio(self) -> float:
        return 0.0 if self.total == 0 else len(self.covered) / self.total


def coverage_of(must_have: Sequence[str], questions: Iterable[str]) -> Coverage:
    """Which must-have requirements the asked questions reach."""
    requirements = [r for r in must_have if key_terms(r)]
    if not requirements:
        return Coverage(total=0, no_requirements=True)
    question_terms = [key_terms(q) for q in questions]
    covered, missing = [], []
    for requirement in requirements:
        terms = key_terms(requirement)
        if any(terms & qt for qt in question_terms):
            covered.append(requirement)
        else:
            missing.append(requirement)
    return Coverage(total=len(requirements), covered=covered, missing=missing)


def next_targets(must_have: Sequence[str], questions: Iterable[str]) -> list[str]:
    """Uncovered requirements, in JD order. The planner asks about these next."""
    return coverage_of(must_have, questions).missing


@dataclass(frozen=True)
class Candidate:
    """A question the interviewer could ask next, with what it is grounded in."""

    question_id: str
    stem: str
    #: The experience the question is about (a company or project name), or None when generic.
    experience: str | None = None


def pick_next(
    must_have: Sequence[str],
    asked: Sequence[Candidate],
    available: Sequence[Candidate],
) -> Candidate | None:
    """The next question for a full run.

    Covers the earliest uncovered must-have first. Among candidates that reach it, prefers one about
    a different experience from the last question, so the interview does not sit on one job for
    several turns. Returns None when nothing available reaches an uncovered requirement.
    """
    asked_ids = {c.question_id for c in asked}
    open_questions = [c for c in available if c.question_id not in asked_ids]
    last_experience = asked[-1].experience if asked else None
    for target in next_targets(must_have, [c.stem for c in asked]):
        reaching = [c for c in open_questions if key_terms(target) & key_terms(c.stem)]
        if not reaching:
            continue
        fresh = [c for c in reaching if c.experience != last_experience or c.experience is None]
        return (fresh or reaching)[0]
    return None
