"""The system records what the candidate says in a mock interview (SPEC-MOCK-INTERVIEW-V2 §3.3).

The interviewer used to be asked to save each answer with a tool, so one forgotten call left the
question "unanswered" in the report. The answer is now written by the service before the model runs,
onto the question on the table: the last question asked, if it was not skipped or swapped away.
Words that arrive when nothing is on the table (the greeting, the self-introduction, "下一题"
after a skip) are not an answer and are not recorded.
"""

from __future__ import annotations

from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.enums import MockSessionStatus
from jc.models.interview import AnswerAttempt
from jc.stores.interview_store import InterviewStore


def records_mock_answer(
    *, turn: str | None, runtime_skill: str, default_skill: str, mock_session_id: str | None
) -> bool:
    """Only the practice skill of the interview turn records answers. A turn that switched to
    another skill of the role, such as archiving a real interview, is not a mock answer."""
    return turn == "mock_session" and runtime_skill == default_skill and bool(mock_session_id)


async def record_mock_answer(
    db: AsyncSession, *, profile_id: str, mock_session_id: str, text: str
) -> str | None:
    """Write `text` as the answer to the question on the table. Returns the attempt id, or None
    when nothing is on the table. Further words on the same question extend the same answer."""
    session = await InterviewStore(db).get_mock_session(mock_session_id)
    if session is None or session.profile_id != profile_id:
        raise PermissionError("Mock session outside this profile")
    words = text.strip()
    if session.status != MockSessionStatus.ACTIVE or not words:
        return None

    state = session.coverage or {}
    asked = state.get("asked") or []
    if not asked or state.get("table_closed"):
        return None
    on_table = asked[-1]
    if on_table.get("skipped"):
        return None

    store = InterviewStore(db)
    question = await store.get_question(on_table["question_id"])
    if question is None or question.profile_id != profile_id:
        return None

    attempt = await store.get_latest_attempt_in_session(question.id, mock_session_id)
    if attempt is not None:
        attempt.user_answer = f"{attempt.user_answer}\n{words}"
        attempt_id = attempt.id
    else:
        attempt_id = new_id("attm")
        await store.add_attempt(AnswerAttempt(
            id=attempt_id,
            question_id=question.id,
            profile_id=profile_id,
            mock_session_id=mock_session_id,
            user_answer=words,
            coach_feedback={},
            reference_answer=None,
            is_best=False,
        ))
        question.attempt_count += 1
    await db.commit()
    return attempt_id
