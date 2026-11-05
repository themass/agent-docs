"""Interview coach and question bank."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.authz import RunScope, require_owned_references
from jc.coach.level import LEVEL_SPECS, LEVELS, level_for_profile
from jc.coach.planner import select_bank_draws
from jc.coach.report_insights import insights
from jc.exceptions import ConflictError, NotFoundError
from jc.models.enums import MAX_REPORT_RUNS, MockReportStatus, MockSessionStatus
from jc.models.interview import InterviewQuestion, InterviewRecord, MockSession
from jc.schemas.coach import (
    AnswerAttemptRequest,
    AnswerAttemptResponse,
    AnswerAttemptSummary,
    BankSearchResponse,
    InterviewListResponse,
    InterviewSaveRequest,
    InterviewSaveResponse,
    InterviewSummary,
    LevelOption,
    LevelRecommendationResponse,
    MockActionResponse,
    MockProgressResponse,
    MockReportResponse,
    MockSessionCreateRequest,
    MockSessionListItem,
    MockSessionListResponse,
    MockSessionQuestion,
    MockSessionResponse,
    QuestionDetailResponse,
    QuestionSummary,
    QuestionUpsertRequest,
)
from jc.services.answer_attempt_service import save_answer_attempt
from jc.services.mock_guard_service import must_have_of
from jc.services.mock_quota_service import MockQuotaService
from jc.services.mock_report_queue import requeue_failed
from jc.services.profile_service import ProfileService
from jc.services.question_bank_service import question_upsert
from jc.stores.interview_store import InterviewStore

logger = logging.getLogger(__name__)


class InterviewService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._store = InterviewStore(db)
        self._profiles = ProfileService(db)

    async def search_bank(
        self,
        profile_id: str,
        *,
        actor: Actor,
        query: str = "",
        company: str | None = None,
        job_id: str | None = None,
        limit: int = 20,
    ) -> BankSearchResponse:
        await self._profiles.get(profile_id, actor=actor)
        rows = await self._store.search_questions(
            profile_id, query=query, company=company, job_id=job_id, limit=limit
        )
        questions: list[QuestionSummary] = []
        for q in rows:
            questions.append(await self._to_question_summary(q))
        return BankSearchResponse(questions=questions)

    async def get_question_detail(
        self, question_id: str, *, actor: Actor
    ) -> QuestionDetailResponse:
        question = await self._store.get_question(question_id)
        if question is None:
            raise NotFoundError("题目不存在或已删除。", code="question_not_found")
        await self._profiles.get(question.profile_id, actor=actor)

        attempts = await self._store.list_attempts_for_question(question_id)
        best_score: int | None = None
        dimension_scores: dict[str, int] | None = None
        if question.best_attempt_id:
            best = await self._store.get_attempt(question.best_attempt_id)
            if best and isinstance(best.coach_feedback, dict):
                raw = best.coach_feedback.get("score")
                if isinstance(raw, (int, float)):
                    best_score = int(raw)
                dims = best.coach_feedback.get("dimensions")
                if isinstance(dims, dict):
                    dimension_scores = {
                        k: int(v) for k, v in dims.items() if isinstance(v, (int, float))
                    }

        return QuestionDetailResponse(
            id=question.id,
            stem=question.stem,
            question_type=question.question_type,
            company=question.company,
            job_id=question.job_id,
            attempt_count=question.attempt_count,
            best_score=best_score,
            dimension_scores=dimension_scores,
            attempts=[
                AnswerAttemptSummary(
                    id=a.id,
                    user_answer=a.user_answer,
                    coach_feedback=a.coach_feedback if isinstance(a.coach_feedback, dict) else None,
                    created_at=a.created_at,
                    is_best=a.is_best,
                )
                for a in attempts
            ],
        )

    async def list_interviews(self, profile_id: str, *, actor: Actor) -> InterviewListResponse:
        await self._profiles.get(profile_id, actor=actor)
        rows = await self._store.list_interviews(profile_id)
        return InterviewListResponse(interviews=[InterviewSummary(
            id=r.id, company=r.company, role_title=r.role_title, interview_date=r.interview_date,
            round=r.round, type=r.type, job_id=r.job_id, result=r.result,
            failure_tags=r.failure_tags or [], notes=r.notes, question_ids=r.question_ids or []
        ) for r in rows])

    async def mock_progress(self, session_id: str, *, actor: UserActor) -> MockProgressResponse:
        from jc.services.mock_guard_service import plan

        session = await self._owned_mock_session(session_id, actor=actor)
        scope = RunScope(db=self._db, user_id=actor.user_id, profile_id=session.profile_id,
                         mock_session_id=session_id)
        return MockProgressResponse(**(await plan(scope, mock_session_id=session_id)))

    async def mock_action(
        self, session_id: str, *, actor: UserActor, action: str, question_id: str
    ) -> MockActionResponse:
        from jc.services import mock_guard_service

        session = await self._owned_mock_session(session_id, actor=actor)
        scope = RunScope(db=self._db, user_id=actor.user_id, profile_id=session.profile_id,
                         mock_session_id=session_id)
        handler = mock_guard_service.skip if action == "skip" else mock_guard_service.swap
        result = await handler(scope, mock_session_id=session_id, question_id=question_id)
        return MockActionResponse(**result)

    async def list_mock_sessions(self, profile_id: str, *, actor: Actor) -> MockSessionListResponse:
        """Finished mock interviews, newest first. Real interviews are listed separately."""
        await self._profiles.get(profile_id, actor=actor)
        stmt = (
            select(MockSession)
            .where(
                MockSession.profile_id == profile_id,
                MockSession.status == MockSessionStatus.COMPLETED,
            )
            .order_by(MockSession.started_at.desc())
        )
        rows = list((await self._db.execute(stmt)).scalars().all())
        items = []
        for row in rows:
            state = dict(row.coverage or {})
            items.append(MockSessionListItem(
                id=row.id,
                style=row.style,
                started_at=row.started_at,
                completed_at=row.completed_at,
                ended_reason=state.get("ended_reason"),
                ended_early=bool(state.get("ended_early")),
                question_count=len(row.question_ids or []),
                has_report=bool(row.report),
            ))
        return MockSessionListResponse(mock_sessions=items)

    async def save_interview(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: InterviewSaveRequest,
    ) -> InterviewSaveResponse:
        await self._profiles.get(profile_id, actor=actor)
        scope = RunScope(
            db=self._db,
            user_id=getattr(actor, "user_id", None),
            profile_id=profile_id,
        )
        await require_owned_references(scope, job_id=body.job_id)
        for qid in body.question_ids:
            question = await self._store.get_question(qid)
            if question is None or question.profile_id != profile_id:
                raise NotFoundError("题目不存在或已删除。", code="question_not_found")
        record = InterviewRecord(
            id=new_id("intr"),
            profile_id=profile_id,
            company=body.company,
            role_title=body.role_title,
            job_id=body.job_id,
            round=body.round,
            type=body.type,
            interview_date=body.interview_date,
            result=body.result,
            failure_tags=body.failure_tags,
            notes=body.notes,
            question_ids=body.question_ids,
            resume_variant_id=None,
        )
        await self._store.create_interview(record)
        await self._db.commit()
        return InterviewSaveResponse(id=record.id)

    async def save_attempt(
        self,
        question_id: str,
        *,
        actor: Actor,
        body: AnswerAttemptRequest,
    ) -> AnswerAttemptResponse:
        question = await self._store.get_question(question_id)
        if question is None:
            raise NotFoundError("题目不存在或已删除。", code="question_not_found")
        await self._profiles.get(question.profile_id, actor=actor)

        user_id = actor.user_id if isinstance(actor, UserActor) else None
        scope = RunScope(db=self._db, user_id=user_id, profile_id=question.profile_id)
        result = await save_answer_attempt(
            scope,
            question_id=question_id,
            user_answer=body.user_answer,
            coach_feedback=body.coach_feedback,
            reference_answer=body.reference_answer,
            mock_session_id=body.mock_session_id,
        )
        return AnswerAttemptResponse(**result)

    async def create_mock_session(
        self,
        *,
        actor: UserActor,
        body: MockSessionCreateRequest,
    ) -> MockSessionResponse:
        profile = await self._profiles.get(body.profile_id, actor=actor)
        scope = RunScope(db=self._db, user_id=actor.user_id, profile_id=body.profile_id)
        await require_owned_references(scope, job_id=body.job_id)
        now = datetime.now(UTC)
        draws: list[str] = []
        if body.mode == "target" and not body.job_id:
            raise ConflictError("目标岗模拟需要先选择岗位；无 JD 可使用练手模式")
        # Decided before the quota is claimed, so a refusal here claims nothing.
        level = body.level
        if level is None:
            recommendation = level_for_profile(profile.payload.experiences, today=date.today())
            if recommendation is None:
                raise ConflictError("请先选择面试级别。", code="mock_level_required")
            level = recommendation.level
        session_id = new_id("mock")
        counted = body.kind == "full"
        if counted:
            # Claimed before the session row exists, so a refused claim leaves nothing behind.
            await MockQuotaService(self._db).claim_full_run(actor.user_id, session_id, now=now)
        bank = await self._store.search_questions(body.profile_id, job_id=body.job_id, limit=30)
        draws = select_bank_draws([(q.id, q.attempt_count) for q in bank], n=1)
        session = MockSession(
            id=session_id,
            profile_id=body.profile_id,
            user_id=actor.user_id,
            mode=body.mode,
            style=body.style,
            level=level,
            quota_counted=counted,
            job_id=body.job_id,
            resume_variant_id=None,
            round=body.round,
            question_ids=list(draws),
            bank_draw_count=len(draws),
            generated_count=0,
            status=MockSessionStatus.ACTIVE,
            started_at=now,
            completed_at=None,
            deerflow_thread_id=None,
        )
        await self._store.create_mock_session(session)
        await self._db.commit()
        return await self._to_mock_response(session)

    async def level_recommendation(
        self, profile_id: str, *, actor: UserActor
    ) -> LevelRecommendationResponse:
        """The four levels, and the one this profile suggests (None when its dates are unusable)."""
        profile = await self._profiles.get(profile_id, actor=actor)
        recommendation = level_for_profile(profile.payload.experiences, today=date.today())
        return LevelRecommendationResponse(
            recommended=recommendation.level if recommendation else None,
            years=recommendation.years if recommendation else None,
            reason=recommendation.reason if recommendation else None,
            levels=[
                LevelOption(
                    key=spec.key, label=spec.label, benchmark=spec.benchmark,
                    years=spec.years, requirement=spec.requirement,
                )
                for spec in (LEVEL_SPECS[key] for key in LEVELS)
            ],
        )

    async def get_mock_session(
        self,
        session_id: str,
        *,
        actor: Actor,
    ) -> MockSessionResponse:
        session = await self._store.get_mock_session(session_id)
        if session is None:
            raise NotFoundError("模拟面试不存在或已删除。", code="mock_session_not_found")
        await self._profiles.get(session.profile_id, actor=actor)
        if isinstance(actor, UserActor) and session.user_id != actor.user_id:
            raise NotFoundError("模拟面试不存在或已删除。", code="mock_session_not_found")
        return await self._to_mock_response(session)

    async def complete_mock_session(
        self, session_id: str, *, actor: UserActor
    ) -> MockSessionResponse:
        """The candidate's own "finish" button: the same guard as the interviewer's, as user_ended.

        The guard is the only writer of a session's end, so an early finish is recorded the same
        way whichever path ends it.
        """
        session = await self._owned_mock_session(session_id, actor=actor)
        if session.status == MockSessionStatus.ACTIVE:
            from jc.services.mock_guard_service import end

            scope = RunScope(db=self._db, user_id=actor.user_id, profile_id=session.profile_id,
                             mock_session_id=session_id)
            await end(scope, mock_session_id=session_id, reason="user_ended")
            await self._db.refresh(session)
        return await self._to_mock_response(session)

    async def _owned_mock_session(self, session_id: str, *, actor: UserActor) -> MockSession:
        session = await self._store.get_mock_session(session_id)
        if session is None:
            raise NotFoundError("模拟面试不存在或已删除。", code="mock_session_not_found")
        await self._profiles.get(session.profile_id, actor=actor)
        if session.user_id != actor.user_id:
            raise NotFoundError("模拟面试不存在或已删除。", code="mock_session_not_found")
        return session

    async def get_mock_report(self, session_id: str, *, actor: UserActor) -> MockReportResponse:
        """Where a finished session's report stands, and the report once it is stored.

        This only reads. The report is produced by the background worker
        (`mock_report_queue`), so opening the page never waits for a model."""
        session = await self._owned_mock_session(session_id, actor=actor)
        state = dict(session.coverage or {})
        base = {
            "mock_session_id": session_id,
            "style": session.style,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "ended_reason": state.get("ended_reason"),
            "ended_early": bool(state.get("ended_early")),
        }
        if session.status == MockSessionStatus.ACTIVE:
            return MockReportResponse(status="active", message="这场模拟面试还在进行中。", **base)
        if session.status != MockSessionStatus.COMPLETED:
            return MockReportResponse(status="active", message="这场模拟面试已取消。", **base)

        if not session.report:
            if session.report_status in (
                MockReportStatus.QUEUED, MockReportStatus.GENERATING
            ):
                return MockReportResponse(
                    status="pending", message="报告正在生成，通常需要一两分钟。", **base
                )
            # Failed, or a completed session no worker will ever pick up: say so rather than
            # leave the page waiting.
            retryable = (
                session.report_status == MockReportStatus.FAILED
                and int(session.report_attempts or 0) < MAX_REPORT_RUNS
            )
            return MockReportResponse(
                status="failed",
                message=session.report_error or "这场面试的报告没有生成。",
                can_retry=retryable,
                **base,
            )

        from jc.services.mock_report_service import session_transcript

        transcript = await session_transcript(self._store, session)
        scope = RunScope(db=self._db, user_id=actor.user_id, profile_id=session.profile_id,
                         mock_session_id=session_id)
        must = await must_have_of(scope, session)
        return _report_view(session, base, transcript, must)

    async def retry_mock_report(self, session_id: str, *, actor: UserActor) -> MockReportResponse:
        """Put a failed report back in the queue. Allowed until every run has been used."""
        session = await self._owned_mock_session(session_id, actor=actor)
        if session.report_status != MockReportStatus.FAILED:
            raise ConflictError("这份报告不需要重新生成。", code="mock_report_not_failed")
        if int(session.report_attempts or 0) >= MAX_REPORT_RUNS:
            raise ConflictError(
                "这份报告已经多次生成失败，不能再重试。", code="mock_report_retry_exhausted"
            )
        if not await requeue_failed(self._db, session_id):
            raise ConflictError("这份报告暂时不能重新生成。", code="mock_report_not_failed")
        await self._db.refresh(session)
        return await self.get_mock_report(session_id, actor=actor)

    async def log_question(
        self,
        profile_id: str,
        *,
        actor: UserActor,
        body: QuestionUpsertRequest,
    ) -> QuestionSummary:
        await self._profiles.get(profile_id, actor=actor)
        scope = RunScope(db=self._db, user_id=actor.user_id, profile_id=profile_id)
        upserted = await question_upsert(
            scope,
            stem=body.stem,
            question_type=body.question_type,
            company=body.company,
            role_title=body.role_title,
            job_id=body.job_id,
            mock_session_id=body.mock_session_id,
            round=body.round,
            source=body.source,
        )
        if body.user_answer and body.user_answer.strip():
            await self.save_attempt(
                upserted["id"],
                actor=actor,
                body=AnswerAttemptRequest(
                    user_answer=body.user_answer.strip(),
                    mock_session_id=body.mock_session_id,
                ),
            )
        question = await self._store.get_question(upserted["id"])
        if question is None:
            raise NotFoundError("题目不存在或已删除。", code="question_not_found")
        return await self._to_question_summary(question)

    async def _to_question_summary(self, q: InterviewQuestion) -> QuestionSummary:
        best_score: int | None = None
        if q.best_attempt_id:
            attempt = await self._store.get_attempt(q.best_attempt_id)
            if attempt and isinstance(attempt.coach_feedback, dict):
                raw = attempt.coach_feedback.get("score")
                if isinstance(raw, (int, float)):
                    best_score = int(raw)
        return QuestionSummary(
            id=q.id,
            stem=q.stem,
            question_type=q.question_type,
            company=q.company,
            job_id=q.job_id,
            tags=q.tags if isinstance(q.tags, list) else [],
            attempt_count=q.attempt_count,
            best_score=best_score,
        )

    async def _to_mock_response(self, session: MockSession) -> MockSessionResponse:
        draw_n = int(session.bank_draw_count or 0)
        drawn_ids = set(list(session.question_ids or [])[:draw_n])
        cards: list[MockSessionQuestion] = []
        for qid in session.question_ids or []:
            q = await self._store.get_question(qid)
            if q is None:
                continue
            cards.append(
                MockSessionQuestion(
                    id=q.id,
                    stem=q.stem,
                    from_bank=q.id in drawn_ids,
                    attempt_count=q.attempt_count,
                )
            )
        return MockSessionResponse(
            id=session.id,
            profile_id=session.profile_id,
            mode=session.mode,
            status=session.status,
            round=session.round,
            job_id=session.job_id,
            started_at=session.started_at,
            level=session.level,
            bank_draw_count=draw_n,
            generated_count=int(session.generated_count or 0),
            questions=cards,
        )


def _report_view(
    session: MockSession,
    base: dict,
    transcript: list[dict[str, str]],
    must_have: list[str],
) -> MockReportResponse:
    """Shape a stored report for the page. A warm-up gets the brief view: the averages and the
    suggestions, without the per-question detail (SPEC §2)."""
    report = session.report or {}
    by_id = {turn["question_id"]: turn for turn in transcript}
    questions = []
    for item in report.get("questions", []):
        qid = item["question_id"]
        turn = by_id.get(qid, {})
        questions.append({
            "question_id": qid,
            "stem": turn.get("stem", ""),
            "answer": turn.get("answer", ""),
            "scores": item.get("scores", {}),
            "evidence": item.get("evidence", {}),
            "praise": item.get("praise"),
            "fixes": item.get("fixes", []),
            "reference": item.get("reference", []),
        })
    stems = {turn["question_id"]: turn["stem"] for turn in transcript}
    derived = insights(report.get("questions", []), report.get("overall", {}), must_have, stems)
    brief = not session.quota_counted
    return MockReportResponse(
        status="ready",
        overall=report.get("overall", {}),
        checks=report.get("checks", {}),
        brief=brief,
        questions=[] if brief else questions,
        trend=derived["trend"],
        coverage=derived["coverage"],
        suggestions=derived["suggestions"],
        **base,
    )