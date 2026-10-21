"""Tool adapters: translate an agent tool call into a service call.

Every function here is thin on purpose. A handler resolves arguments, delegates to a
service, and shapes the result for the model. Business rules, database writes and
LLM calls live in `jc.services`; nothing in `jc.services` may import this module,
because a tool surface is an inbound adapter and inbound adapters are never
dependencies of the logic they expose.

The dispatcher below is also where a tool's *shape* is pinned. `jc_profile_patch` has
no `apply` argument to strip anymore — proposing and applying are different service
functions, and only the proposing one is reachable from here.
"""

from __future__ import annotations

from typing import Any

from agentkit.common.ids import new_id

from jc.authz import RunScope, require_owned_profile, require_owned_references
from jc.models.interview import InterviewRecord
from jc.models.job import Job
from jc.schemas.profile_payload import ProfilePayload
from jc.services.answer_attempt_service import save_answer_attempt
from jc.services.fit_score_service import FitScoreService
from jc.services.jd_parser_service import JdParserService
from jc.services.profile_patch_service import propose_patch
from jc.services.question_bank_service import question_upsert
from jc.stores.interview_store import InterviewStore
from jc.stores.job_store import JobStore
from jc.stores.profile_store import ProfileStore


async def profile_get(
    scope: RunScope, profile_id: str | None = None, *, section: str | None = None,
    field_path: str | None = None, offset: int = 0, limit: int = 5,
    text_offset: int | None = None, text_limit: int = 4000,
) -> dict[str, Any]:
    await require_owned_profile(scope, profile_id)
    pid = profile_id or scope.profile_id
    if not pid:
        raise ValueError("profile_id required")
    store = ProfileStore(scope.db)
    profile = await store.get_by_id(pid)
    if profile is None:
        raise ValueError("Profile not found")
    if not scope.user_id or profile.user_id != scope.user_id:
        raise PermissionError("Not your profile")
    if field_path and section is None:
        raise ValueError("section required with field_path")
    if section is not None:
        from jc.domain.profile_context import read_profile_section

        return {"id": profile.id, "version": profile.version, "status": profile.status,
                **read_profile_section(profile.payload, section=section, field_path=field_path,
                                       offset=offset, limit=limit,
                                       text_offset=text_offset, text_limit=text_limit)}
    # Legacy clients keep their full-read contract. Agent guidance uses explicit sections.
    return {"id": profile.id, "version": profile.version,
            "status": profile.status, "payload": profile.payload}


async def profile_patch(
    scope: RunScope,
    patch: dict[str, Any],
    *,
    profile_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Propose a profile edit. The model cannot apply one — see ADR-003.

    There is no `apply` parameter to pass. Applying a confirmed patch is a separate
    service function whose only caller is the confirm endpoint, so the boundary is
    enforced by what this adapter can reach rather than by argument filtering.
    """
    return await propose_patch(
        scope,
        patch,
        profile_id=profile_id,
        session_id=session_id,
    )


async def bank_search_questions(
    scope: RunScope,
    *,
    query: str = "",
    company: str | None = None,
    job_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")
    store = InterviewStore(scope.db)
    rows = await store.search_questions(
        scope.profile_id,
        query=query,
        company=company,
        job_id=job_id,
        limit=max(1, min(limit, 50)),
    )
    return {
        "questions": [
            {
                "id": q.id,
                "stem": q.stem,
                "question_type": q.question_type,
                "company": q.company,
                "job_id": q.job_id,
                "tags": q.tags,
                "attempt_count": q.attempt_count,
            }
            for q in rows
        ]
    }


async def mock_session_history(
    scope: RunScope,
    *,
    mock_session_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    from jc.services.question_bank_service import mock_session_history as _mock_session_history

    return await _mock_session_history(scope, mock_session_id=mock_session_id, limit=limit)


async def interview_save(scope: RunScope, record: dict[str, Any]) -> dict[str, Any]:
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")
    from datetime import date

    store = InterviewStore(scope.db)
    await require_owned_references(scope, job_id=record.get("job_id"))
    for qid in record.get("question_ids") or []:
        question = await store.get_question(qid)
        if question is None or question.profile_id != scope.profile_id:
            raise PermissionError("Question outside this profile")
    row = InterviewRecord(
        id=new_id("intr"),
        profile_id=scope.profile_id,
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
    await scope.db.commit()
    return {"id": row.id}


async def answer_save_attempt(
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
    return await save_answer_attempt(
        scope,
        question_id=question_id,
        user_answer=user_answer,
        coach_feedback=coach_feedback,
        reference_answer=reference_answer,
        mock_session_id=mock_session_id,
        question_stem=question_stem,
        company=company,
        job_id=job_id,
    )


async def job_fetch(scope: RunScope, *, url: str, render: bool = False) -> dict[str, Any]:
    """Read-only, owned-profile scoped; no parsing or persistence side effects."""
    await require_owned_profile(scope)
    from jc.services.jd_fetch_service import JdFetchService
    return (await JdFetchService().fetch(url, render=render)).as_dict()


async def job_parse(
    scope: RunScope,
    *,
    raw_text: str,
    source_url: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")
    parser = JdParserService()
    parsed = await parser.parse(raw_text=raw_text)
    result: dict[str, Any] = {"parsed": parsed.model_dump(mode="json")}
    if save:
        job = Job(
            id=new_id("job"),
            profile_id=scope.profile_id,
            company=parsed.company or "待确认公司",
            title=parsed.role_title,
            source_url=source_url,
            raw_text=raw_text[:50_000],
            requirements=parsed.model_dump(mode="json"),
        )
        await JobStore(scope.db).create(job)
        await scope.db.commit()
        result["job_id"] = job.id
    return result


async def fit_score(
    scope: RunScope,
    *,
    job_id: str | None = None,
    raw_jd: str | None = None,
) -> dict[str, Any]:
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")
    profile_row = await ProfileStore(scope.db).get_by_id(scope.profile_id)
    if profile_row is None:
        raise ValueError("Profile not found")
    profile = ProfilePayload.model_validate(profile_row.payload or {})
    profile_version = profile_row.version

    parser = JdParserService()
    scorer = FitScoreService()
    job_store = JobStore(scope.db)
    job: Job | None = None

    if job_id:
        job = await job_store.get_by_id(job_id)
        if job is None or job.profile_id != scope.profile_id:
            raise ValueError("Job not found")
        from jc.schemas.job import JDParseResult

        jd = JDParseResult.model_validate(job.requirements or {})
        if not jd.role_title:
            jd = await parser.parse(raw_text=job.raw_text)
    elif raw_jd:
        jd = await parser.parse(raw_text=raw_jd)
    else:
        raise ValueError("job_id or raw_jd required")

    result = await scorer.score(profile=profile, jd=jd)
    result = result.model_copy(update={"evidence_profile_version": profile_version})
    if job is not None:
        job.fit_score = result.score
        job.fit_recommendation = result.recommendation
        job.fit_gaps = result.gaps
        job.fit_blockers = result.blockers
        job.fit_report = {
            "evidence_profile_version": result.evidence_profile_version,
            "requirement_evidence": [item.model_dump() for item in result.requirement_evidence],
            "summary": result.summary,
            "elevate_hints": result.elevate_hints,
            "dimensions": result.dimensions,
            "legitimacy": result.legitimacy,
        }
        await job_store.save(job)
        await scope.db.commit()
        result = result.model_copy(update={"job_id": job.id})
    return result.model_dump(mode="json")


async def apply_pipeline(
    scope: RunScope,
    *,
    job_id: str | None = None,
    raw_text: str | None = None,
    source_url: str | None = None,
    elevation_level: str = "elevated",
    export_format: str = "pdf",
    create_application: bool = False,
) -> dict[str, Any]:
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")
    if not scope.user_id:
        raise PermissionError("Login required for apply pipeline")

    from agentkit.web.auth import UserActor

    from jc.schemas.job import ApplyPipelineRequest
    from jc.services.apply_pipeline_service import ApplyPipelineService

    actor = UserActor(user_id=scope.user_id, session_id="mcp")
    service = ApplyPipelineService(scope.db)
    result = await service.run(
        scope.profile_id,
        actor=actor,
        body=ApplyPipelineRequest(
            job_id=job_id,
            raw_text=raw_text,
            source_url=source_url,
            elevation_level=elevation_level,
            export_format=export_format,
            create_application=create_application,
        ),
        trace_id=scope.session_id,
    )
    return result.model_dump(mode="json")


async def resume_review(
    scope: RunScope,
    *,
    draft_id: str | None = None,
    elevation_level: str = "elevated",
) -> dict[str, Any]:
    await require_owned_profile(scope)
    if not scope.profile_id:
        raise ValueError("profile_id required")

    from jc.models.enums import ReviewerStatus
    from jc.services.resume_reviewer import ResumeReviewer
    from jc.stores.resume_store import ResumeStore

    store = ResumeStore(scope.db)
    draft = await store.get_draft_by_id(draft_id) if draft_id else None
    if draft is None:
        draft = await store.get_latest_draft(scope.profile_id, elevation_level=elevation_level)
    if draft is None:
        raise ValueError("No resume draft to review — run elevate or apply pipeline first")

    if draft.profile_id != scope.profile_id:
        raise PermissionError("Draft outside this profile")
    profile = await require_owned_profile(scope)
    review = await ResumeReviewer().review(sections=draft.sections, source_profile=profile.payload)
    draft.reviewer_status = review.status
    draft.reviewer_notes = review.notes
    await scope.db.commit()

    status = (
        review.status.value if isinstance(review.status, ReviewerStatus) else str(review.status)
    )
    return {
        "status": status,
        "passed": review.status == ReviewerStatus.PASSED,
        "notes": review.notes,
        "issues": review.issues,
        "draft_id": draft.id,
    }


async def intake_plan(scope: RunScope, *, limit: int = 6) -> dict[str, Any]:
    """What this profile still needs, as the interview plan the panel shows.

    Why the agent needs a tool for this at all
    ------------------------------------------
    Before this existed the coach was told the shortfall as *prose* in its turn
    message (`coach_shortfall_for`), which is a snapshot taken before the turn began.
    So after the agent wrote two answers down with `jc_profile_patch` it had no way to
    learn that the profile now clears the bar — it either kept interviewing a profile
    that was already generatable, or claimed it was done while two bullets short. The
    plan is server state; an agent that writes to it has to be able to read it back.

    Read-only, and it reads the same `build_intake_plan` the panel does. A second
    notion of "what is missing" is the failure this shares a function to prevent: the
    sidebar and the panel telling one user two different things about one profile.
    """
    profile = await require_owned_profile(scope)
    from jc.domain.role_families import resolve_role_family
    from jc.services.intake_service import answered_question_ids
    from jc.services.profile_intake import build_intake_plan

    payload = ProfilePayload.model_validate(profile.payload or {})
    family = resolve_role_family(
        override=payload.preferences.role_family,
        profile_titles=tuple(e.title for e in payload.experiences[:2]),
    )
    plan = build_intake_plan(
        payload,
        role_family=family,
        answered_ids=answered_question_ids(payload),
        limit=max(1, min(int(limit), 12)),
    )
    return {
        "profile_id": profile.id,
        "version": profile.version,
        "mode": plan.mode,
        "role_family": plan.role_family,
        "role_label": plan.role_label,
        "can_generate": plan.can_generate,
        "blocking": list(plan.blocking),
        "answered_count": plan.answered_count,
        "questions": [
            {
                "id": q.id,
                "target_path": q.target_path,
                "label": q.label,
                "question": q.question,
                "rationale": q.rationale,
                "required": q.required,
            }
            for q in plan.questions
        ],
        "answered": [
            {"question_id": a.question_id, "label": a.label, "answer": a.answer}
            for a in plan.answered
        ],
    }


async def intake_record(
    scope: RunScope,
    *,
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write interview answers the user just gave in chat into the profile.

    Why this is not `jc_profile_patch`
    ----------------------------------
    `jc_profile_patch` is the confirmation-gated path for editing a profile the user
    has already reviewed: the model proposes a merge, the user approves it in the UI.
    That gate is right there and wrong here. During intake the model is not proposing
    content — it is transcribing what the user said one message ago, into a slot the
    plan already named. Routing that through a confirm card asks the user to re-approve
    their own sentence, which is why the interview-by-chat path stalled: every answer
    became a card, and the agent could not see whether the card was ever accepted.

    What keeps it safe is narrower than a confirm gate and stricter:

    1. **Only paths the current plan is asking about.** `question_id` must match a
       pending question, and `target_path` must be the one that question named. A model
       cannot invent a path, cannot answer a question that is not open, and cannot
       reach a field the interview does not cover.
    2. **Verbatim.** The text is stored as given, through the same
       `record_intake_answers` the panel uses.
    3. **Visible.** Every write comes back labelled in the user's words, and the panel
       reads the same profile — so the user sees it land.

    This is a deliberate exception to "the model never writes without confirmation",
    and it is bounded by the plan rather than by trust in the model.
    """
    profile = await require_owned_profile(scope)
    from jc.domain.role_families import resolve_role_family
    from jc.schemas.intake import IntakeAnswerInput
    from jc.services.intake_service import answered_question_ids, record_intake_answers
    from jc.services.profile_intake import build_intake_plan

    if not answers:
        raise ValueError("answers must not be empty")

    payload = ProfilePayload.model_validate(profile.payload or {})
    family = resolve_role_family(
        override=payload.preferences.role_family,
        profile_titles=tuple(e.title for e in payload.experiences[:2]),
    )
    # The full plan, not the truncated one the panel renders: an answer to a question
    # that is pending but sits past the display limit is still a legitimate answer.
    plan = build_intake_plan(
        payload,
        role_family=family,
        answered_ids=answered_question_ids(payload),
        limit=10_000,
    )
    open_questions = {q.id: q for q in plan.questions}

    inputs: list[IntakeAnswerInput] = []
    for raw in answers:
        qid = str(raw.get("question_id") or "").strip()
        text = str(raw.get("answer") or "").strip()
        if not qid or not text:
            raise ValueError("each answer needs question_id and answer")
        question = open_questions.get(qid)
        if question is None:
            # Either already answered or never asked. Both are the same mistake from
            # here: the agent is writing against a plan it has not re-read.
            raise ValueError(
                f"question_id {qid} is not open on this profile; "
                "call jc_intake_plan for the current questions"
            )
        declared = str(raw.get("target_path") or "").strip()
        if declared and declared != question.target_path:
            raise ValueError(
                f"target_path for {qid} must be {question.target_path}"
            )
        inputs.append(
            IntakeAnswerInput(
                question_id=qid,
                target_path=question.target_path,
                question=question.question,
                answer=text,
            )
        )

    applied, stored = record_intake_answers(payload, inputs)
    row = await ProfileStore(scope.db).get_by_id(profile.id)
    if row is None:
        raise ValueError("Profile not found")
    row.payload = payload.model_dump(mode="json")
    row.contact_name = payload.contact.name
    row.summary_text = (payload.summary or "")[:512] or None
    row.version += 1
    await scope.db.commit()

    after = build_intake_plan(
        payload,
        role_family=family,
        answered_ids=answered_question_ids(payload),
        limit=3,
    )
    return {
        "profile_id": profile.id,
        "version": row.version,
        "stored": stored,
        "applied": [{"path": w.path, "label": w.label, "value": w.value} for w in applied],
        "can_generate": after.can_generate,
        "blocking": list(after.blocking),
        "next_questions": [
            {"id": q.id, "target_path": q.target_path, "question": q.question}
            for q in after.questions
        ],
    }


async def profile_photo_set(
    scope: RunScope, *, message_id: str | None = None, attachment_index: int | None = None,
) -> dict[str, Any]:
    """Request user-controlled cropping of a session-owned chat image."""
    from jc.services.agent_photo_service import request_photo_crop

    return await request_photo_crop(scope, message_id=message_id, attachment_index=attachment_index)


TOOL_HANDLERS = {
    "jc_profile_photo_set": profile_photo_set,
    "jc_profile_get": profile_get,
    "jc_profile_patch": profile_patch,
    "jc_bank_search_questions": bank_search_questions,
    "jc_interview_save": interview_save,
    "jc_answer_save_attempt": answer_save_attempt,
    "jc_job_fetch": job_fetch,
    "jc_job_parse": job_parse,
    "jc_fit_score": fit_score,
    "jc_apply_pipeline": apply_pipeline,
    "jc_question_upsert": question_upsert,
    "jc_mock_session_history": mock_session_history,
    "jc_resume_review": resume_review,
    "jc_intake_plan": intake_plan,
    "jc_intake_record": intake_record,
}


async def dispatch_tool(
    scope: RunScope,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown tool: {name}")
    if name == "jc_profile_photo_set":
        return await handler(
            scope, message_id=arguments.get("message_id"),
            attachment_index=arguments.get("attachment_index"),
        )
    if name == "jc_profile_get":
        return await handler(
            scope, arguments.get("profile_id"),
            section=arguments.get("section") or "overview",
            **{key: arguments[key] for key in (
                "field_path", "offset", "limit", "text_offset", "text_limit",
            ) if key in arguments},
        )
    if name == "jc_profile_patch":
        return await handler(
            scope,
            arguments.get("patch", {}),
            profile_id=arguments.get("profile_id"),
            session_id=scope.session_id,
        )
    if name == "jc_bank_search_questions":
        return await handler(
            scope,
            query=arguments.get("query", ""),
            company=arguments.get("company"),
            job_id=arguments.get("job_id"),
            limit=int(arguments.get("limit", 10)),
        )
    if name == "jc_interview_save":
        return await handler(scope, arguments.get("record", arguments))
    if name == "jc_answer_save_attempt":
        return await handler(
            scope,
            question_id=arguments.get("question_id"),
            user_answer=arguments["user_answer"],
            coach_feedback=arguments.get("coach_feedback"),
            reference_answer=arguments.get("reference_answer"),
            mock_session_id=arguments.get("mock_session_id"),
            question_stem=arguments.get("question_stem"),
            company=arguments.get("company"),
            job_id=arguments.get("job_id"),
        )
    if name == "jc_job_parse":
        return await handler(
            scope,
            raw_text=arguments["raw_text"],
            source_url=arguments.get("source_url"),
            save=bool(arguments.get("save", True)),
        )
    if name == "jc_fit_score":
        return await handler(
            scope,
            job_id=arguments.get("job_id"),
            raw_jd=arguments.get("raw_jd"),
        )
    if name == "jc_apply_pipeline":
        return await handler(
            scope,
            job_id=arguments.get("job_id"),
            raw_text=arguments.get("raw_text"),
            source_url=arguments.get("source_url"),
            elevation_level=str(arguments.get("elevation_level", "elevated")),
            export_format=str(arguments.get("export_format", "pdf")),
            create_application=arguments.get("create_application", False),
        )
    if name == "jc_question_upsert":
        return await handler(
            scope,
            stem=arguments["stem"],
            question_type=str(arguments.get("question_type", "behavioral")),
            company=arguments.get("company"),
            role_title=arguments.get("role_title"),
            job_id=arguments.get("job_id"),
            mock_session_id=arguments.get("mock_session_id"),
            tags=arguments.get("tags"),
            round=arguments.get("round"),
        )
    if name == "jc_mock_session_history":
        return await handler(
            scope,
            mock_session_id=arguments.get("mock_session_id"),
            limit=int(arguments.get("limit", 20)),
        )
    if name == "jc_resume_review":
        return await handler(
            scope,
            draft_id=arguments.get("draft_id"),
            elevation_level=str(arguments.get("elevation_level", "elevated")),
        )
    if name == "jc_intake_plan":
        return await handler(scope, limit=int(arguments.get("limit", 6)))
    if name == "jc_intake_record":
        return await handler(scope, answers=list(arguments.get("answers") or []))
    raise ValueError(f"Unhandled tool: {name}")
