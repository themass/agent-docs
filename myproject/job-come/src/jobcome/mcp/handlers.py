"""In-process MCP tool handlers (shared with stdio server)."""

from __future__ import annotations

import json
from typing import Any

from agentkit.common.ids import new_id

from jobcome.mcp.context import McpRunContext
from jobcome.models.interview import AnswerAttempt, InterviewRecord
from jobcome.models.job import Job
from jobcome.schemas.profile_payload import ProfilePayload
from jobcome.coach.feedback import normalize_coach_feedback
from jobcome.mcp.question_upsert import question_upsert
from jobcome.services.fit_score_service import FitScoreService
from jobcome.services.jd_parser_service import JdParserService
from jobcome.services.patch_confirm_service import create_pending, pop_pending
from jobcome.stores.interview_store import InterviewStore
from jobcome.stores.job_store import JobStore
from jobcome.stores.profile_store import ProfileStore


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


async def profile_get(ctx: McpRunContext, profile_id: str | None = None) -> dict[str, Any]:
    pid = profile_id or ctx.profile_id
    if not pid:
        raise ValueError("profile_id required")
    store = ProfileStore(ctx.db)
    profile = await store.get_by_id(pid)
    if profile is None:
        raise ValueError("Profile not found")
    if ctx.user_id and profile.user_id and profile.user_id != ctx.user_id:
        raise PermissionError("Not your profile")
    return {
        "id": profile.id,
        "version": profile.version,
        "status": profile.status,
        "payload": profile.payload,
    }


async def profile_patch(
    ctx: McpRunContext,
    patch: dict[str, Any],
    *,
    profile_id: str | None = None,
    apply: bool = False,
    confirm_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    pid = profile_id or ctx.profile_id
    if confirm_id:
        pending = await pop_pending(confirm_id)
        if pending is None:
            raise ValueError("Confirm request expired or not found")
        if ctx.user_id and pending.user_id != ctx.user_id:
            raise PermissionError("Not your confirm request")
        pid = pending.profile_id
        patch = pending.patch
        apply = True

    if not pid:
        raise ValueError("profile_id required")
    store = ProfileStore(ctx.db)
    profile = await store.get_by_id(pid)
    if profile is None:
        raise ValueError("Profile not found")
    if ctx.user_id and profile.user_id and profile.user_id != ctx.user_id:
        raise PermissionError("Not your profile")

    current = dict(profile.payload or {})
    merged = _deep_merge(dict(current), patch)
    payload = ProfilePayload.model_validate(merged)

    if not apply:
        if not ctx.user_id:
            raise PermissionError("Login required to patch profile")
        pending = await create_pending(
            session_id=session_id or ctx.session_id or "",
            user_id=ctx.user_id,
            profile_id=pid,
            patch=patch,
            preview={
                "profile_id": pid,
                "version_before": profile.version,
                "patch_keys": list(patch.keys()),
                "merged": payload.model_dump(mode="json"),
            },
        )
        return {
            "status": "pending_confirm",
            "confirm_id": pending.confirm_id,
            "profile_id": pid,
            "patch": patch,
            "preview": pending.preview,
            "message": "Profile patch requires user confirmation in the UI.",
        }

    profile.payload = payload.model_dump(mode="json")
    profile.contact_name = payload.contact.name
    profile.summary_text = (payload.summary or "")[:512] or None
    profile.version += 1
    await ctx.db.commit()
    return {
        "status": "applied",
        "id": profile.id,
        "version": profile.version,
        "payload": profile.payload,
    }


async def bank_search_questions(
    ctx: McpRunContext,
    *,
    query: str = "",
    company: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    store = InterviewStore(ctx.db)
    rows = await store.search_questions(
        ctx.profile_id,
        query=query,
        company=company,
        limit=min(limit, 50),
    )
    return {
        "questions": [
            {
                "id": q.id,
                "stem": q.stem,
                "question_type": q.question_type,
                "company": q.company,
                "tags": q.tags,
                "attempt_count": q.attempt_count,
            }
            for q in rows
        ]
    }


async def interview_save(ctx: McpRunContext, record: dict[str, Any]) -> dict[str, Any]:
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    from datetime import date

    store = InterviewStore(ctx.db)
    row = InterviewRecord(
        id=new_id("intr"),
        profile_id=ctx.profile_id,
        company=record["company"],
        role_title=record["role_title"],
        job_id=record.get("job_id"),
        round=record.get("round", "first"),
        type=record.get("type", "target"),
        interview_date=date.fromisoformat(record["interview_date"]),
        result=record.get("result"),
        failure_tags=record.get("failure_tags") or [],
        notes=record.get("notes"),
        question_ids=record.get("question_ids") or [],
        resume_variant_id=record.get("resume_variant_id"),
    )
    await store.create_interview(row)
    await ctx.db.commit()
    return {"id": row.id}


async def answer_save_attempt(
    ctx: McpRunContext,
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
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    if not question_id and question_stem:
        upserted = await question_upsert(
            ctx,
            stem=question_stem,
            company=company,
            job_id=job_id,
            mock_session_id=mock_session_id,
        )
        question_id = upserted["id"]
    if not question_id:
        raise ValueError("question_id or question_stem required")
    store = InterviewStore(ctx.db)
    question = await store.get_question(question_id)
    if question is None or question.profile_id != ctx.profile_id:
        raise ValueError("Question not found")

    feedback = normalize_coach_feedback(coach_feedback)
    attempt = AnswerAttempt(
        id=new_id("attm"),
        question_id=question_id,
        profile_id=ctx.profile_id,
        mock_session_id=mock_session_id,
        user_answer=user_answer,
        coach_feedback=feedback,
        reference_answer=reference_answer,
        is_best=False,
    )
    await store.add_attempt(attempt)
    question.attempt_count += 1
    if feedback and feedback.get("score", 0) >= 8:
        attempt.is_best = True
        question.best_attempt_id = attempt.id
    await ctx.db.commit()
    return {"attempt_id": attempt.id, "question_id": question_id}


async def job_parse(
    ctx: McpRunContext,
    *,
    raw_text: str,
    source_url: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    parser = JdParserService()
    parsed = await parser.parse(raw_text=raw_text)
    result: dict[str, Any] = {"parsed": parsed.model_dump(mode="json")}
    if save:
        job = Job(
            id=new_id("job"),
            profile_id=ctx.profile_id,
            company=parsed.company or "待确认公司",
            title=parsed.role_title,
            source_url=source_url,
            raw_text=raw_text[:50_000],
            requirements=parsed.model_dump(mode="json"),
        )
        await JobStore(ctx.db).create(job)
        await ctx.db.commit()
        result["job_id"] = job.id
    return result


async def fit_score(
    ctx: McpRunContext,
    *,
    job_id: str | None = None,
    raw_jd: str | None = None,
) -> dict[str, Any]:
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    profile_row = await ProfileStore(ctx.db).get_by_id(ctx.profile_id)
    if profile_row is None:
        raise ValueError("Profile not found")
    profile = ProfilePayload.model_validate(profile_row.payload or {})

    parser = JdParserService()
    scorer = FitScoreService()
    job_store = JobStore(ctx.db)
    job: Job | None = None

    if job_id:
        job = await job_store.get_by_id(job_id)
        if job is None or job.profile_id != ctx.profile_id:
            raise ValueError("Job not found")
        from jobcome.schemas.job import JDParseResult

        jd = JDParseResult.model_validate(job.requirements or {})
        if not jd.role_title:
            jd = await parser.parse(raw_text=job.raw_text)
    elif raw_jd:
        jd = await parser.parse(raw_text=raw_jd)
    else:
        raise ValueError("job_id or raw_jd required")

        result = await scorer.score(profile=profile, jd=jd)
        if job is not None:
            job.fit_score = result.score
            job.fit_recommendation = result.recommendation
            job.fit_gaps = result.gaps
            job.fit_blockers = result.blockers
            job.fit_report = {
                "summary": result.summary,
                "elevate_hints": result.elevate_hints,
                "dimensions": result.dimensions,
                "legitimacy": result.legitimacy,
            }
            await job_store.save(job)
            await ctx.db.commit()
            result = result.model_copy(update={"job_id": job.id})
        return result.model_dump(mode="json")


async def apply_pipeline(
    ctx: McpRunContext,
    *,
    job_id: str | None = None,
    raw_text: str | None = None,
    source_url: str | None = None,
    elevation_level: str = "elevated",
    export_format: str = "pdf",
    create_application: bool = True,
) -> dict[str, Any]:
    if not ctx.profile_id:
        raise ValueError("profile_id required")
    if not ctx.user_id:
        raise PermissionError("Login required for apply pipeline")

    from agentkit.web.auth import UserActor

    from jobcome.schemas.job import ApplyPipelineRequest
    from jobcome.services.apply_pipeline_service import ApplyPipelineService

    actor = UserActor(user_id=ctx.user_id, session_id="mcp")
    service = ApplyPipelineService(ctx.db)
    result = await service.run(
        ctx.profile_id,
        actor=actor,
        body=ApplyPipelineRequest(
            job_id=job_id,
            raw_text=raw_text,
            source_url=source_url,
            elevation_level=elevation_level,
            export_format=export_format,
            create_application=create_application,
        ),
        trace_id=ctx.session_id,
    )
    return result.model_dump(mode="json")


async def resume_review(
    ctx: McpRunContext,
    *,
    draft_id: str | None = None,
    elevation_level: str = "elevated",
) -> dict[str, Any]:
    if not ctx.profile_id:
        raise ValueError("profile_id required")

    from jobcome.models.enums import ReviewerStatus
    from jobcome.services.resume_reviewer import ResumeReviewer
    from jobcome.stores.resume_store import ResumeStore

    store = ResumeStore(ctx.db)
    draft = await store.get_draft_by_id(draft_id) if draft_id else None
    if draft is None:
        draft = await store.get_latest_draft(ctx.profile_id, elevation_level=elevation_level)
    if draft is None:
        raise ValueError("No resume draft to review — run elevate or apply pipeline first")

    review = await ResumeReviewer().review(sections=draft.sections)
    draft.reviewer_status = review.status
    draft.reviewer_notes = review.notes
    await ctx.db.commit()

    status = review.status.value if isinstance(review.status, ReviewerStatus) else str(review.status)
    return {
        "status": status,
        "passed": review.status == ReviewerStatus.PASSED,
        "notes": review.notes,
        "issues": review.issues,
        "draft_id": draft.id,
    }


TOOL_HANDLERS = {
    "jobcome_profile_get": profile_get,
    "jobcome_profile_patch": profile_patch,
    "jobcome_bank_search_questions": bank_search_questions,
    "jobcome_interview_save": interview_save,
    "jobcome_answer_save_attempt": answer_save_attempt,
    "jobcome_job_parse": job_parse,
    "jobcome_fit_score": fit_score,
    "jobcome_apply_pipeline": apply_pipeline,
    "jobcome_question_upsert": question_upsert,
    "jobcome_resume_review": resume_review,
}


async def dispatch_tool(
    ctx: McpRunContext,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    if name == "jobcome_profile_get":
        return await handler(ctx, arguments.get("profile_id"))
    if name == "jobcome_profile_patch":
        args = dict(arguments)
        args.pop("apply", None)
        return await handler(
            ctx,
            args.get("patch", {}),
            profile_id=args.get("profile_id"),
            session_id=ctx.session_id,
        )
    if name == "jobcome_bank_search_questions":
        return await handler(
            ctx,
            query=arguments.get("query", ""),
            company=arguments.get("company"),
            limit=int(arguments.get("limit", 10)),
        )
    if name == "jobcome_interview_save":
        return await handler(ctx, arguments.get("record", arguments))
    if name == "jobcome_answer_save_attempt":
        return await handler(
            ctx,
            question_id=arguments.get("question_id"),
            user_answer=arguments["user_answer"],
            coach_feedback=arguments.get("coach_feedback"),
            reference_answer=arguments.get("reference_answer"),
            mock_session_id=arguments.get("mock_session_id"),
            question_stem=arguments.get("question_stem"),
            company=arguments.get("company"),
            job_id=arguments.get("job_id"),
        )
    if name == "jobcome_job_parse":
        return await handler(
            ctx,
            raw_text=arguments["raw_text"],
            source_url=arguments.get("source_url"),
            save=bool(arguments.get("save", True)),
        )
    if name == "jobcome_fit_score":
        return await handler(
            ctx,
            job_id=arguments.get("job_id"),
            raw_jd=arguments.get("raw_jd"),
        )
    if name == "jobcome_apply_pipeline":
        return await handler(
            ctx,
            job_id=arguments.get("job_id"),
            raw_text=arguments.get("raw_text"),
            source_url=arguments.get("source_url"),
            elevation_level=str(arguments.get("elevation_level", "elevated")),
            export_format=str(arguments.get("export_format", "pdf")),
            create_application=bool(arguments.get("create_application", True)),
        )
    if name == "jobcome_question_upsert":
        return await handler(
            ctx,
            stem=arguments["stem"],
            question_type=str(arguments.get("question_type", "behavioral")),
            company=arguments.get("company"),
            role_title=arguments.get("role_title"),
            job_id=arguments.get("job_id"),
            mock_session_id=arguments.get("mock_session_id"),
            tags=arguments.get("tags"),
        )
    if name == "jobcome_resume_review":
        return await handler(
            ctx,
            draft_id=arguments.get("draft_id"),
            elevation_level=str(arguments.get("elevation_level", "elevated")),
        )
    raise ValueError(f"Unhandled tool: {name}")
