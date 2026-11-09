"""The turns of a mock interview as the reviewer and the report read them.

One definition, so the history the reviewer reads, the transcript the report is checked against and
the page all agree on what was asked, in what order, and which question a follow-up belongs to.

The order is the order the questions were asked (`coverage.asked`), not the order they were first
filed on the session: a question drawn from the bank at the start and never asked is not a turn, and
a follow-up sits right after its main question. A session from before the guards recorded nothing
but question ids; it has no `asked` list, and each of its questions is read as a main question.
"""

from __future__ import annotations

from dataclasses import dataclass

from jc.models.interview import MockSession
from jc.stores.interview_store import InterviewStore


@dataclass(frozen=True)
class Turn:
    question_id: str
    stem: str
    #: The candidate's answer in this session. Empty for a question skipped or not yet answered.
    answer: str
    question_type: str = "behavioral"
    #: "main" or "followup".
    kind: str = "main"
    #: For a follow-up, the main question it follows up.
    parent_question_id: str | None = None
    skipped: bool = False
    #: The must-have names the interviewer tagged the question with.
    tags: list[str] | None = None

    def as_transcript_entry(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "stem": self.stem,
            "tags": list(self.tags or []),
            "answer": self.answer,
            "kind": self.kind,
            "parent_question_id": self.parent_question_id,
            "skipped": self.skipped,
        }


def _asked(session: MockSession) -> list[dict]:
    entries = (session.coverage or {}).get("asked")
    if entries:
        return [dict(entry) for entry in entries]
    return [
        {"question_id": question_id, "kind": "main", "parent_question_id": None}
        for question_id in session.question_ids or []
    ]


async def session_turns(store: InterviewStore, session: MockSession) -> list[Turn]:
    """Every question that was put to the candidate in this session, in the order it was asked."""
    turns: list[Turn] = []
    for entry in _asked(session):
        question_id = entry["question_id"]
        question = await store.get_question(question_id)
        skipped = bool(entry.get("skipped"))
        attempt = None if skipped else await store.get_latest_attempt_in_session(
            question_id, session.id
        )
        turns.append(Turn(
            question_id=question_id,
            stem=question.stem if question is not None else "",
            answer=(attempt.user_answer or "") if attempt is not None else "",
            question_type=question.question_type if question is not None else "behavioral",
            kind=entry.get("kind") or "main",
            parent_question_id=entry.get("parent_question_id"),
            skipped=skipped,
            tags=list(question.tags or []) if question is not None else None,
        ))
    return turns
