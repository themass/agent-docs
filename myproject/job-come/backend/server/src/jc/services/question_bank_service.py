"""Interview question bank writes — shared by the coach API and the agent tool surface."""

from __future__ import annotations

from agentkit.common.ids import new_id

from typing import Any

from jc.authz import RunScope, require_owned_profile, require_owned_references
from jc.models.enums import QuestionSource
from jc.models.interview import InterviewQuestion
from jc.stores.interview_store import InterviewStore


async def _attach_to_mock(
    store: InterviewStore,
    *,
    profile_id: str,
    mock_session_id: str,
    question_id: str,
    created: bool,
) -> None:
    session = await store.get_mock_session(mock_session_id)
    if session is None or session.profile_id != profile_id:
        return
    qids = list(session.question_ids or [])
    if question_id in qids:
        return
    qids.append(question_id)
    session.question_ids = qids
    if created:
        session.generated_count = int(session.generated_count or 0) + 1


async def question_upsert(
    scope: RunScope,
    *,
    stem: str,
    question_type: str = "behavioral",
    company: str | None = None,
    role_title: str | None = None,
    job_id: str | None = None,
    mock_session_id: str | None = None,
    tags: list[str] | None = None,
    round: str | None = None,
    source: str = "mock",
) -> dict:
    mock_session_id = mock_session_id or scope.mock_session_id
    job_id = job_id or scope.job_id
    await require_owned_profile(scope)
    await require_owned_references(scope, job_id=job_id, mock_session_id=mock_session_id)
    source_kind = QuestionSource(source)
    text = stem.strip()
    if not text:
        raise ValueError("stem required")

    store = InterviewStore(scope.db)
    existing = await store.find_question_by_stem(scope.profile_id, text, company=company)
    if existing is not None:
        if job_id and not existing.job_id:
            existing.job_id = job_id
        if mock_session_id:
            await _attach_to_mock(
                store,
                profile_id=scope.profile_id,
                mock_session_id=mock_session_id,
                question_id=existing.id,
                created=False,
            )
        await scope.db.commit()
        return {
            "id": existing.id,
            "stem": existing.stem,
            "created": False,
            "attempt_count": existing.attempt_count,
        }

    row = InterviewQuestion(
        id=new_id("iq"),
        profile_id=scope.profile_id,
        stem=text,
        question_type=question_type,
        source=source_kind,
        company=company,
        role_title=role_title,
        job_id=job_id,
        round=round,
        tags=tags or [],
    )
    await store.create_question(row)
    if mock_session_id:
        await _attach_to_mock(
            store,
            profile_id=scope.profile_id,
            mock_session_id=mock_session_id,
            question_id=row.id,
            created=True,
        )
    await scope.db.commit()
    return {"id": row.id, "stem": row.stem, "created": True, "attempt_count": 0}


async def mock_session_history(
    scope: RunScope,
    *,
    mock_session_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Read back what has already been asked/answered this mock session.

    Pairs with `jc_question_upsert` / `jc_answer_save_attempt`, which only write.
    Without this, a model that loses the early turns of a long mock interview to
    context-window summarization has no way to recover "what did you already ask
    me" — it either guesses from the LLM-generated summary or asks the user to
    repeat themselves. This reads the session's authoritative question order
    straight from `jc_mock_session.question_ids` plus each question's latest
    attempt, so the agent can re-ground itself regardless of what survived
    compaction.
    """
    mock_session_id = mock_session_id or scope.mock_session_id
    if not mock_session_id:
        raise ValueError("mock_session_id required")
    await require_owned_profile(scope)
    await require_owned_references(scope, mock_session_id=mock_session_id)
    store = InterviewStore(scope.db)
    session = await store.get_mock_session(mock_session_id)
    if session is None or session.profile_id != scope.profile_id:
        raise PermissionError("Mock session outside this profile")

    turns: list[dict[str, Any]] = []
    for qid in list(session.question_ids or [])[-max(1, min(limit, 50)) :]:
        question = await store.get_question(qid)
        if question is None:
            continue
        attempt = await store.get_latest_attempt_for_question(qid)
        turns.append(
            {
                "question_id": question.id,
                "stem": question.stem,
                "question_type": question.question_type,
                "user_answer": attempt.user_answer if attempt else None,
                "coach_feedback": attempt.coach_feedback if attempt else None,
                "attempt_count": question.attempt_count,
            }
        )
    return {
        "mock_session_id": session.id,
        "status": session.status,
        "mode": session.mode,
        "turns": turns,
    }
