"""JC MCP server — stdio transport for DeerFlow.

Identity (user_id/profile_id/session_id/job_id/mock_session_id) arrives as
explicit tool arguments, not process environment variables. The stdio
transport's MCP session is pooled and reused across many turns and many
users (see deerflow.mcp.session_pool); a value written into os.environ at
turn start is a *process-global* mutation that a concurrent turn for a
different user can read or clobber mid-flight. Explicit arguments carried on
the JSON-RPC `tools/call` request are scoped to that one call.

These identity arguments are declared on every tool so FastMCP's generated
JSON schema includes them — the model may see them and could in principle
try to fill them in. That is not the trust boundary: `jc.mcp.identity_interceptor`
overwrites every `jc_*` identity argument with the value resolved from this
run's LangGraph runtime context before the call reaches this module, so
whatever the model supplies here is always replaced server-side. A caller
that bypasses the interceptor (direct stdio client, unit test) gets a
`RunScope` with unset identity, which every guard in `jc.authz.ownership`
fails closed on — never another user's data.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from jc.authz import RunScope
from jc.db.session import AsyncSessionLocal
from jc.mcp.handlers import (
    answer_save_attempt,
    bank_search_questions,
    interview_save,
    mock_session_history,
    profile_get,
    profile_patch,
)

mcp = FastMCP("jc")


def _scope(
    db,
    *,
    jc_user_id: str | None,
    jc_profile_id: str | None,
    jc_session_id: str | None,
    jc_job_id: str | None = None,
    jc_mock_session_id: str | None = None,
) -> RunScope:
    """Build a RunScope from this call's explicit identity arguments.

    No fallback to os.environ: a tool invoked without the identity
    interceptor (bypassing normal dispatch) gets an unauthenticated scope
    rather than silently inheriting whatever turn last wrote the process
    environment.
    """
    return RunScope(
        db=db,
        user_id=jc_user_id or None,
        profile_id=jc_profile_id or None,
        session_id=jc_session_id or None,
        job_id=jc_job_id or None,
        mock_session_id=jc_mock_session_id or None,
    )


@mcp.tool()
async def jc_profile_get(
    profile_id: str | None = None,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
    section: str | None = "overview",
    field_path: str | None = None,
    offset: int = 0,
    limit: int = 5,
    text_offset: int | None = None,
    text_limit: int = 4000,
) -> str:
    """Read profile JSON."""
    async with AsyncSessionLocal() as db:
        result = await profile_get(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            profile_id, section=section, field_path=field_path, offset=offset, limit=limit,
            text_offset=text_offset, text_limit=text_limit,
        )
        await db.commit()
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_profile_patch(
    patch: dict,
    profile_id: str | None = None,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    """Patch profile fields."""
    async with AsyncSessionLocal() as db:
        scope = _scope(
            db,
            jc_user_id=jc_user_id,
            jc_profile_id=jc_profile_id,
            jc_session_id=jc_session_id,
        )
        result = await profile_patch(
            scope,
            patch,
            profile_id=profile_id,
            session_id=scope.session_id,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_bank_search_questions(
    query: str = "",
    company: str | None = None,
    limit: int = 10,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        result = await bank_search_questions(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            query=query,
            company=company,
            limit=limit,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_interview_save(
    record: dict,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        result = await interview_save(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            record,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_mock_session_history(
    mock_session_id: str | None = None,
    limit: int = 20,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
    jc_job_id: str | None = None,
    jc_mock_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        result = await mock_session_history(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
                jc_job_id=jc_job_id,
                jc_mock_session_id=jc_mock_session_id,
            ),
            mock_session_id=mock_session_id,
            limit=limit,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_answer_save_attempt(
    user_answer: str,
    question_id: str | None = None,
    question_stem: str | None = None,
    coach_feedback: dict | None = None,
    reference_answer: str | None = None,
    mock_session_id: str | None = None,
    company: str | None = None,
    job_id: str | None = None,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
    jc_job_id: str | None = None,
    jc_mock_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        result = await answer_save_attempt(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
                jc_job_id=jc_job_id,
                jc_mock_session_id=jc_mock_session_id,
            ),
            question_id=question_id,
            user_answer=user_answer,
            coach_feedback=coach_feedback,
            reference_answer=reference_answer,
            mock_session_id=mock_session_id,
            question_stem=question_stem,
            company=company,
            job_id=job_id,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_job_fetch(
    url: str,
    render: bool = False,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        from jc.mcp.handlers import job_fetch

        result = await job_fetch(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            url=url,
            render=render,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_job_parse(
    raw_text: str,
    source_url: str | None = None,
    save: bool = True,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        from jc.mcp.handlers import job_parse

        result = await job_parse(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            raw_text=raw_text,
            source_url=source_url,
            save=save,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_fit_score(
    job_id: str | None = None,
    raw_jd: str | None = None,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
    jc_job_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        from jc.mcp.handlers import fit_score

        result = await fit_score(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
                jc_job_id=jc_job_id,
            ),
            job_id=job_id,
            raw_jd=raw_jd,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_apply_pipeline(
    job_id: str | None = None,
    raw_text: str | None = None,
    source_url: str | None = None,
    elevation_level: str = "elevated",
    export_format: str = "pdf",
    create_application: bool = False,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
    jc_job_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        from jc.mcp.handlers import apply_pipeline

        result = await apply_pipeline(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
                jc_job_id=jc_job_id,
            ),
            job_id=job_id,
            raw_text=raw_text,
            source_url=source_url,
            elevation_level=elevation_level,
            export_format=export_format,
            create_application=create_application,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_question_upsert(
    stem: str,
    question_type: str = "behavioral",
    company: str | None = None,
    role_title: str | None = None,
    job_id: str | None = None,
    mock_session_id: str | None = None,
    tags: list[str] | None = None,
    round: str | None = None,
    source: str = "mock",
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
    jc_job_id: str | None = None,
    jc_mock_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        from jc.services.question_bank_service import question_upsert

        result = await question_upsert(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
                jc_job_id=jc_job_id,
                jc_mock_session_id=jc_mock_session_id,
            ),
            stem=stem,
            question_type=question_type,
            company=company,
            role_title=role_title,
            job_id=job_id,
            mock_session_id=mock_session_id,
            tags=tags,
            round=round,
            source=source,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_intake_plan(
    limit: int = 6,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    """What this profile still needs before a resume can be generated."""
    async with AsyncSessionLocal() as db:
        from jc.mcp.handlers import intake_plan

        result = await intake_plan(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            limit=limit,
        )
        await db.commit()
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_intake_record(
    answers: list[dict],
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    """Write the user's interview answers into the profile, verbatim."""
    async with AsyncSessionLocal() as db:
        from jc.mcp.handlers import intake_record

        result = await intake_record(
            _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
            answers=answers,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jc_resume_review(
    draft_id: str | None = None,
    elevation_level: str = "elevated",
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    """Review this run's resume draft before exporting."""
    from jc.mcp.handlers import resume_review

    async with AsyncSessionLocal() as db:
        return json.dumps(
            await resume_review(
                _scope(
                db,
                jc_user_id=jc_user_id,
                jc_profile_id=jc_profile_id,
                jc_session_id=jc_session_id,
            ),
                draft_id=draft_id,
                elevation_level=elevation_level,
            ),
            ensure_ascii=False,
        )


@mcp.tool()
async def jc_profile_photo_set(
    message_id: str | None = None,
    attachment_index: int | None = None,
    jc_user_id: str | None = None,
    jc_profile_id: str | None = None,
    jc_session_id: str | None = None,
) -> str:
    """Prepare a chat image for resume photo cropping. User must crop and save in UI."""
    from jc.mcp.handlers import profile_photo_set

    async with AsyncSessionLocal() as db:
        result = await profile_photo_set(
            _scope(db, jc_user_id=jc_user_id, jc_profile_id=jc_profile_id, jc_session_id=jc_session_id),
            message_id=message_id, attachment_index=attachment_index,
        )
        return json.dumps(result, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
