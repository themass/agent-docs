"""Interview question upsert for coach flywheel."""

from __future__ import annotations

from agentkit.common.ids import new_id

from jobcome.mcp.context import McpRunContext
from jobcome.models.enums import QuestionSource
from jobcome.models.interview import InterviewQuestion
from jobcome.stores.interview_store import InterviewStore


async def question_upsert(
    ctx: McpRunContext,
    *,
    stem: str,
    question_type: str = "behavioral",
    company: str | None = None,
    role_title: str | None = None,
    job_id: str | None = None,
    mock_session_id: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    text = stem.strip()
    if not text:
        raise ValueError("stem required")

    store = InterviewStore(ctx.db)
    existing = await store.find_question_by_stem(ctx.profile_id, text, company=company)
    if existing is not None:
        return {
            "id": existing.id,
            "stem": existing.stem,
            "created": False,
            "attempt_count": existing.attempt_count,
        }

    row = InterviewQuestion(
        id=new_id("iq"),
        profile_id=ctx.profile_id,
        stem=text,
        question_type=question_type,
        source=QuestionSource.MOCK,
        company=company,
        role_title=role_title,
        job_id=job_id,
        tags=tags or [],
    )
    await store.create_question(row)
    if mock_session_id:
        session = await store.get_mock_session(mock_session_id)
        if session is not None and session.profile_id == ctx.profile_id:
            qids = list(session.question_ids or [])
            if row.id not in qids:
                qids.append(row.id)
            session.question_ids = qids
    await ctx.db.commit()
    return {"id": row.id, "stem": row.stem, "created": True, "attempt_count": 0}
