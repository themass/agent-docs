"""JobCome MCP server — stdio transport for DeerFlow."""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from jobcome.db.session import AsyncSessionLocal
from jobcome.mcp.context import McpRunContext
from jobcome.mcp.handlers import (
    answer_save_attempt,
    bank_search_questions,
    interview_save,
    profile_get,
    profile_patch,
)

mcp = FastMCP("jobcome")


def _env_ctx(db) -> McpRunContext:
    return McpRunContext(
        db=db,
        user_id=os.environ.get("JOB_COME_MCP_USER_ID"),
        profile_id=os.environ.get("JOB_COME_MCP_PROFILE_ID"),
        session_id=os.environ.get("JOB_COME_MCP_SESSION_ID"),
        job_id=os.environ.get("JOB_COME_MCP_JOB_ID"),
    )


@mcp.tool()
async def jobcome_profile_get(profile_id: str | None = None) -> str:
    """Read profile JSON."""
    async with AsyncSessionLocal() as db:
        result = await profile_get(_env_ctx(db), profile_id)
        await db.commit()
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_profile_patch(patch: dict, profile_id: str | None = None) -> str:
    """Patch profile fields."""
    async with AsyncSessionLocal() as db:
        result = await profile_patch(
            _env_ctx(db),
            patch,
            profile_id=profile_id,
            session_id=os.environ.get("JOB_COME_MCP_SESSION_ID"),
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_bank_search_questions(
    query: str = "",
    company: str | None = None,
    limit: int = 10,
) -> str:
    async with AsyncSessionLocal() as db:
        result = await bank_search_questions(
            _env_ctx(db), query=query, company=company, limit=limit
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_interview_save(record: dict) -> str:
    async with AsyncSessionLocal() as db:
        result = await interview_save(_env_ctx(db), record)
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_answer_save_attempt(
    user_answer: str,
    question_id: str | None = None,
    question_stem: str | None = None,
    coach_feedback: dict | None = None,
    reference_answer: str | None = None,
    mock_session_id: str | None = None,
    company: str | None = None,
    job_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        result = await answer_save_attempt(
            _env_ctx(db),
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
async def jobcome_job_parse(
    raw_text: str,
    source_url: str | None = None,
    save: bool = True,
) -> str:
    async with AsyncSessionLocal() as db:
        from jobcome.mcp.handlers import job_parse

        result = await job_parse(
            _env_ctx(db),
            raw_text=raw_text,
            source_url=source_url,
            save=save,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_fit_score(job_id: str | None = None, raw_jd: str | None = None) -> str:
    async with AsyncSessionLocal() as db:
        from jobcome.mcp.handlers import fit_score

        result = await fit_score(_env_ctx(db), job_id=job_id, raw_jd=raw_jd)
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_apply_pipeline(
    job_id: str | None = None,
    raw_text: str | None = None,
    source_url: str | None = None,
    elevation_level: str = "elevated",
    export_format: str = "pdf",
    create_application: bool = True,
) -> str:
    async with AsyncSessionLocal() as db:
        from jobcome.mcp.handlers import apply_pipeline

        result = await apply_pipeline(
            _env_ctx(db),
            job_id=job_id,
            raw_text=raw_text,
            source_url=source_url,
            elevation_level=elevation_level,
            export_format=export_format,
            create_application=create_application,
        )
        return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def jobcome_question_upsert(
    stem: str,
    question_type: str = "behavioral",
    company: str | None = None,
    role_title: str | None = None,
    job_id: str | None = None,
    mock_session_id: str | None = None,
) -> str:
    async with AsyncSessionLocal() as db:
        from jobcome.mcp.question_upsert import question_upsert

        result = await question_upsert(
            _env_ctx(db),
            stem=stem,
            question_type=question_type,
            company=company,
            role_title=role_title,
            job_id=job_id,
            mock_session_id=mock_session_id,
        )
        return json.dumps(result, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
