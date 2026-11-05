"""Where interview questions, and the reference material for them, come from.

Today there is one source: the candidate's own bank (`personal`). The curated question bank and the
profile library are meant to come later, and they plug in here. A source can

- `search` for candidate questions (what the interviewer may ask), and
- say what it knows about a question (`reference`): what a strong, adequate and weak answer looks
  like, the follow-ups worth asking, and the signs to look for. The reviewer reads this next to the
  candidate's answer.

Nothing else changes when a source is added: the search tool lists its questions with the source's
name, the reviewer's history carries its reference material, and the report is checked the same way.

A source that fails is skipped, not fatal. A search or a history read that depends on an optional
source must still answer without it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from jc.authz.scope import RunScope

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchRequest:
    query: str = ""
    company: str | None = None
    job_id: str | None = None
    #: The role family the profile belongs to (`jc.coach.role_family`), when known.
    role_family: str | None = None
    #: junior | mid | senior | expert, when the session has one.
    level: str | None = None
    limit: int = 10


@dataclass(frozen=True)
class QuestionCandidate:
    stem: str
    question_type: str = "behavioral"
    #: The name of the source this came from.
    source: str = "personal"
    #: The id of the question in the candidate's own bank, when it is already there.
    question_id: str | None = None
    company: str | None = None
    job_id: str | None = None
    tags: list[Any] = field(default_factory=list)
    attempt_count: int = 0
    difficulty: str | None = None
    #: The source's own key for this question, for a later `reference` lookup.
    reference_key: str | None = None


@dataclass(frozen=True)
class QuestionReference:
    """What a source knows about judging an answer to one question. Reviewer-facing."""

    source: str
    strong: str = ""
    adequate: str = ""
    weak: str = ""
    follow_ups: list[str] = field(default_factory=list)
    signals_positive: list[str] = field(default_factory=list)
    signals_negative: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "strong": self.strong,
            "adequate": self.adequate,
            "weak": self.weak,
            "follow_ups": list(self.follow_ups),
            "signals_positive": list(self.signals_positive),
            "signals_negative": list(self.signals_negative),
        }


@runtime_checkable
class QuestionSource(Protocol):
    name: str

    async def search(self, scope: RunScope, request: SearchRequest) -> list[QuestionCandidate]:
        """Candidate questions for this request, best first."""

    async def reference(
        self, scope: RunScope, *, stem: str, question_id: str
    ) -> QuestionReference | None:
        """Reference material for a question that was asked, or None. Optional for a source."""


class PersonalBankSource:
    """The candidate's own bank: the questions they have logged or been asked before."""

    name = "personal"

    async def search(self, scope: RunScope, request: SearchRequest) -> list[QuestionCandidate]:
        from jc.authz import require_owned_profile
        from jc.stores.interview_store import InterviewStore

        await require_owned_profile(scope)
        rows = await InterviewStore(scope.db).search_questions(
            scope.profile_id,
            query=request.query,
            company=request.company,
            job_id=request.job_id,
            limit=request.limit,
        )
        return [
            QuestionCandidate(
                stem=q.stem,
                question_type=q.question_type,
                source=self.name,
                question_id=q.id,
                company=q.company,
                job_id=q.job_id,
                tags=list(q.tags or []),
                attempt_count=q.attempt_count,
            )
            for q in rows
        ]

    async def reference(
        self, scope: RunScope, *, stem: str, question_id: str
    ) -> QuestionReference | None:
        return None


_REGISTRY: list[QuestionSource] = [PersonalBankSource()]


def registered() -> list[QuestionSource]:
    return list(_REGISTRY)


def register(source: QuestionSource) -> None:
    """Add a source, or replace the one that has the same name."""
    for index, existing in enumerate(_REGISTRY):
        if existing.name == source.name:
            _REGISTRY[index] = source
            return
    _REGISTRY.append(source)


def reset(to: list[QuestionSource] | None = None) -> None:
    """Put the registry back (tests)."""
    _REGISTRY[:] = to if to is not None else [PersonalBankSource()]


async def search_all(scope: RunScope, request: SearchRequest) -> list[QuestionCandidate]:
    """Every source's candidates, the same question once (the first source to name it wins)."""
    seen: set[str] = set()
    found: list[QuestionCandidate] = []
    for source in registered():
        try:
            candidates = await source.search(scope, request)
        except PermissionError:
            raise
        except Exception:  # noqa: BLE001 — an optional source must not break the search
            logger.warning("question source %s failed to search", source.name, exc_info=True)
            continue
        for candidate in candidates:
            key = " ".join(candidate.stem.split())
            if key in seen:
                continue
            seen.add(key)
            found.append(candidate)
    return found[: max(1, request.limit)]


async def reference_for(
    scope: RunScope, *, stem: str, question_id: str
) -> QuestionReference | None:
    """The first source that has reference material for this question."""
    for source in registered():
        lookup = getattr(source, "reference", None)
        if lookup is None:
            continue
        try:
            reference = await lookup(scope, stem=stem, question_id=question_id)
        except Exception:  # noqa: BLE001 — optional; the history must stay readable
            logger.warning("question source %s failed to look up a reference", source.name,
                           exc_info=True)
            continue
        if reference is not None:
            return reference
    return None
