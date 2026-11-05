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
from jc.services.mock_turns import session_turns
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
    raw: dict[str, Any],
    *,
    answers: dict[str, str],
    profile_text: str,
    followups: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Check and normalise a reviewer report. Raises ValueError for a malformed report.

    `answers` holds the main questions only; `followups` maps a follow-up's id to its main
    question, so a report that scores a follow-up is told which question to score instead."""
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
        if followups and qid in followups:
            raise ValueError(
                f"question {qid!r} is a follow-up (追问) of {followups[qid]!r}: score the main "
                f"question {followups[qid]!r} and quote the follow-up's answer as evidence"
            )
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


async def session_transcript(store: InterviewStore, session: MockSession) -> list[dict[str, Any]]:
    """Every question put to the candidate, in the order it was asked, with the candidate's latest
    answer and which main question a follow-up belongs to (see `jc.services.mock_turns`).

    A skipped question has an empty answer, so the reviewer may score it only as null
    (AGENTS-DESIGN §4.2: skipped counts as unanswered).
    """
    return [turn.as_transcript_entry() for turn in await session_turns(store, session)]


def answers_by_main_question(transcript: list[dict[str, Any]]) -> dict[str, str]:
    """What a score may be quoted from: a main question's own answer and its follow-ups' answers.

    Only main questions are scored. A follow-up is how the interviewer dug into the main question,
    so what the candidate said there is evidence for it."""
    answers = {t["question_id"]: t["answer"] for t in transcript if t["kind"] != "followup"}
    for turn in transcript:
        parent = turn["parent_question_id"]
        if turn["kind"] == "followup" and parent in answers and turn["answer"]:
            answers[parent] = f"{answers[parent]}\n{turn['answer']}".strip()
    return answers


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
    # The reviewer run is started for one session; a report for another one is refused.
    if scope.mock_session_id and scope.mock_session_id != mock_session_id:
        raise PermissionError("Report is for another mock session")
    session = await store.get_mock_session(mock_session_id)
    if session is None or session.profile_id != scope.profile_id:
        raise PermissionError("Mock session outside this profile")
    if session.status != "completed":
        raise ValueError("a report can only be written after the session has ended")

    transcript = await session_transcript(store, session)
    answers = answers_by_main_question(transcript)
    followups = {t["question_id"]: t["parent_question_id"]
                 for t in transcript if t["kind"] == "followup"}
    profile_text = await profile_payload_text(scope)
    report = validate_report(raw, answers=answers, profile_text=profile_text,
                             followups=followups)
    session.report = report
    await scope.db.flush()
    await scope.db.commit()
    return {
        "mock_session_id": mock_session_id,
        "checks": report["checks"],
        "overall": report["overall"],
    }
