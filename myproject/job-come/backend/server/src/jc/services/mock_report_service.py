"""Reviewer output for a finished mock session, checked before it is stored.

The reviewer is a model, so its output is checked, not trusted. Two checks run in code:
- a score is kept only when its evidence quote appears in the user's own answer; otherwise the
  score becomes "cannot judge" and is counted in `checks.rejected_evidence`;
- a reference fact is "sourced" only when its source phrase appears in the profile; otherwise it is
  "pending" and counted in `checks.pending_facts`.
The overall averages are computed here, never taken from the model.
"""

from __future__ import annotations

import json
import re
from typing import Any

from jc.authz.ownership import require_owned_profile
from jc.authz.scope import RunScope
from jc.models.interview import MockSession
from jc.models.profile import Profile
from jc.stores.interview_store import InterviewStore

DIMENSIONS = ("structure", "relevance", "depth", "communication", "reflection")
SEVERITIES = ("must", "suggest", "nit")


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _as_score(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
        raise ValueError(f"score must be an integer 1-10 or null, got {value!r}")
    return value


def validate_report(
    raw: dict[str, Any], *, answers: dict[str, str], profile_text: str
) -> dict[str, Any]:
    """Check and normalise a reviewer report. Raises ValueError for a malformed report."""
    items = raw.get("questions")
    if not isinstance(items, list) or not items:
        raise ValueError("report needs a non-empty questions list")

    rejected = 0
    pending = 0
    totals: dict[str, list[int]] = {d: [] for d in DIMENSIONS}
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        qid = item.get("question_id")
        if qid not in answers:
            raise ValueError(f"question {qid!r} is not part of this session")
        if qid in seen:
            raise ValueError(f"question {qid!r} appears twice")
        seen.add(qid)
        answer = _squash(answers[qid])
        scores_in = item.get("scores") or {}
        evidence_in = item.get("evidence") or {}

        scores: dict[str, int | None] = {}
        evidence: dict[str, str] = {}
        for dim in DIMENSIONS:
            score = _as_score(scores_in.get(dim))
            quote = evidence_in.get(dim)
            if score is None:
                scores[dim] = None
                continue
            if not quote or _squash(str(quote)) not in answer:
                rejected += 1
                scores[dim] = None
                continue
            scores[dim] = score
            evidence[dim] = str(quote)
            totals[dim].append(score)

        references = []
        for fact in item.get("reference") or []:
            source = str(fact.get("source") or "").strip()
            sourced = bool(source) and _squash(source) in _squash(profile_text)
            if not sourced:
                pending += 1
            references.append({
                "text": str(fact.get("text") or ""),
                "source": source or None,
                "status": "sourced" if sourced else "pending",
            })

        fixes = []
        for fix in item.get("fixes") or []:
            severity = fix.get("severity")
            if severity not in SEVERITIES:
                raise ValueError(f"fix severity must be one of {SEVERITIES}")
            fixes.append({"severity": severity, "text": str(fix.get("text") or "")})

        questions.append({
            "question_id": qid,
            "scores": scores,
            "evidence": evidence,
            "praise": str(item.get("praise") or "") or None,
            "fixes": fixes,
            "reference": references,
        })

    overall = {
        dim: round(sum(values) / len(values), 1) if values else None
        for dim, values in totals.items()
    }
    return {
        "overall": overall,
        "questions": questions,
        "checks": {"rejected_evidence": rejected, "pending_facts": pending},
    }


async def session_transcript(store: InterviewStore, session: MockSession) -> list[dict[str, str]]:
    """Every question of the session, in order, with the candidate's latest answer.

    A skipped question has an empty answer, so the reviewer may score it only as null
    (AGENTS-DESIGN §4.2: skipped counts as unanswered).
    """
    turns = []
    for qid in session.question_ids or []:
        question = await store.get_question(qid)
        attempt = await store.get_latest_attempt_for_question(qid)
        turns.append({
            "question_id": qid,
            "stem": question.stem if question is not None else "",
            "answer": (attempt.user_answer or "") if attempt is not None else "",
        })
    return turns


async def profile_payload_text(scope: RunScope) -> str:
    profile = await scope.db.get(Profile, scope.profile_id)
    return json.dumps(profile.payload if profile else {}, ensure_ascii=False)


async def write_report(
    scope: RunScope, *, mock_session_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Validate a reviewer report and store it on a completed session the caller owns."""
    await require_owned_profile(scope)
    store = InterviewStore(scope.db)
    # Not require_owned_references: that guard refuses closed sessions, and the report is written
    # precisely after the session has closed.
    session = await store.get_mock_session(mock_session_id)
    if session is None or session.profile_id != scope.profile_id:
        raise PermissionError("Mock session outside this profile")
    if session.status != "completed":
        raise ValueError("a report can only be written after the session has ended")

    transcript = await session_transcript(store, session)
    answers = {turn["question_id"]: turn["answer"] for turn in transcript}
    profile_text = await profile_payload_text(scope)
    report = validate_report(raw, answers=answers, profile_text=profile_text)
    session.report = report
    await scope.db.flush()
    await scope.db.commit()
    return {
        "mock_session_id": mock_session_id,
        "checks": report["checks"],
        "overall": report["overall"],
    }
