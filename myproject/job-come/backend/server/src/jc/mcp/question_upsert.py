"""Interview question upsert for coach flywheel."""

from __future__ import annotations

from agentkit.common.ids import new_id

from jc.mcp.context import McpRunContext, require_owned_profile, require_owned_references
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
    ctx: McpRunContext,
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
    mock_session_id = mock_session_id or ctx.mock_session_id
    job_id = job_id or ctx.job_id
    await require_owned_profile(ctx)
    await require_owned_references(ctx, job_id=job_id, mock_session_id=mock_session_id)
    source_kind = QuestionSource(source)
    text = stem.strip()
    if not text:
        raise ValueError("stem required")

    store = InterviewStore(ctx.db)
    existing = await store.find_question_by_stem(ctx.profile_id, text, company=company)
    if existing is not None:
        if job_id and not existing.job_id:
            existing.job_id = job_id
        if mock_session_id:
            await _attach_to_mock(
                store,
                profile_id=ctx.profile_id,
                mock_session_id=mock_session_id,
                question_id=existing.id,
                created=False,
            )
        await ctx.db.commit()
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
            profile_id=ctx.profile_id,
            mock_session_id=mock_session_id,
            question_id=row.id,
            created=True,
        )
    await ctx.db.commit()
    return {"id": row.id, "stem": row.stem, "created": True, "attempt_count": 0}
