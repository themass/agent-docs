"""Practice answer attempts — one implementation behind both the API and the tool.

The coach API and the `jc_answer_save_attempt` tool used to be two paths into this,
with the service reaching back into the tool handler to avoid duplicating the
best-attempt bookkeeping. That import was the wrong direction: a tool surface is an
inbound adapter and nothing inbound should be a dependency of the business logic.
The logic lives here now and both callers come down to it.
"""

from __future__ import annotations

from typing import Any

from agentkit.common.ids import new_id

from jc.authz import RunScope, require_owned_profile, require_owned_references
from jc.coach.feedback import normalize_coach_feedback
from jc.models.interview import AnswerAttempt
from jc.services.question_bank_service import question_upsert
from jc.stores.interview_store import InterviewStore


async def save_answer_attempt(
    scope: RunScope,
    *,
    question_id: str | None = None,
    user_answer: str,
    coach_feedback: dict[str, Any] | None = None,
    reference_answer: str | None = None,
    mock_session_id: str | None = None,
    question_stem: str | None = None,
    company: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    mock_session_id = mock_session_id or scope.mock_session_id
    job_id = job_id or scope.job_id
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")
    if not question_id and question_stem:
        upserted = await question_upsert(
            scope,
            stem=question_stem,
            company=company,
            job_id=job_id,
            mock_session_id=mock_session_id,
        )
        question_id = upserted["id"]
    if not question_id:
        raise ValueError("question_id or question_stem required")
    store = InterviewStore(scope.db)
    question = await store.get_question(question_id)
    if question is None or question.profile_id != scope.profile_id:
        raise ValueError("Question not found")

    await require_owned_references(scope, job_id=job_id, mock_session_id=mock_session_id)
    if not user_answer.strip():
        raise ValueError("user_answer must not be empty")
    feedback = normalize_coach_feedback(coach_feedback)
    attempt = AnswerAttempt(
        id=new_id("attm"),
        question_id=question_id,
        profile_id=scope.profile_id,
        mock_session_id=mock_session_id,
        user_answer=user_answer,
        coach_feedback=feedback,
        reference_answer=reference_answer,
        is_best=False,
    )
    await store.add_attempt(attempt)
    question.attempt_count += 1
    score = feedback.get("score")
    best = await store.get_attempt(question.best_attempt_id) if question.best_attempt_id else None
    best_score = (best.coach_feedback or {}).get("score", 0) if best else 0
    if isinstance(score, (int, float)) and 1 <= score <= 10 and score > best_score:
        if best:
            best.is_best = False
        attempt.is_best = True
        question.best_attempt_id = attempt.id
    await scope.db.commit()
    return {"attempt_id": attempt.id, "question_id": question_id}
