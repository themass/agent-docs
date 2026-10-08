"""Interview coach and question bank."""

from __future__ import annotations

from datetime import UTC, datetime

from agentkit.common.ids import new_id
from agentkit.web.auth import Actor, UserActor
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.coach.planner import select_bank_draws
from jobcome.exceptions import NotFoundError
from jobcome.mcp.context import McpRunContext
from jobcome.mcp.question_upsert import question_upsert
from jobcome.models.enums import MockSessionStatus
from jobcome.models.interview import InterviewQuestion, InterviewRecord, MockSession
from jobcome.schemas.coach import (
    AnswerAttemptRequest,
    AnswerAttemptResponse,
    AnswerAttemptSummary,
    BankSearchResponse,
    InterviewSaveRequest,
    InterviewSaveResponse,
    MockSessionCreateRequest,
    MockSessionQuestion,
    MockSessionResponse,
    QuestionDetailResponse,
    QuestionSummary,
    QuestionUpsertRequest,
)
from jobcome.services.profile_service import ProfileService
from jobcome.stores.interview_store import InterviewStore


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
            raise NotFoundError("Question not found")
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

    async def save_interview(
        self,
        profile_id: str,
        *,
        actor: Actor,
        body: InterviewSaveRequest,
    ) -> InterviewSaveResponse:
        await self._profiles.get(profile_id, actor=actor)
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
            raise NotFoundError("Question not found")
        await self._profiles.get(question.profile_id, actor=actor)

        from jobcome.mcp.context import McpRunContext
        from jobcome.mcp.handlers import answer_save_attempt

        user_id = actor.user_id if isinstance(actor, UserActor) else None
        ctx = McpRunContext(db=self._db, user_id=user_id, profile_id=question.profile_id)
        result = await answer_save_attempt(
            ctx,
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
        await self._profiles.get(body.profile_id, actor=actor)
        now = datetime.now(UTC)
        draws: list[str] = []
        if body.job_id:
            bank = await self._store.search_questions(
                body.profile_id, job_id=body.job_id, limit=30
            )
            draws = select_bank_draws(
                [(q.id, q.attempt_count) for q in bank],
                n=1,
            )
        session = MockSession(
            id=new_id("mock"),
            profile_id=body.profile_id,
            user_id=actor.user_id,
            mode=body.mode,
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

    async def get_mock_session(
        self,
        session_id: str,
        *,
        actor: Actor,
    ) -> MockSessionResponse:
        session = await self._store.get_mock_session(session_id)
        if session is None:
            raise NotFoundError("Mock session not found")
        await self._profiles.get(session.profile_id, actor=actor)
        if isinstance(actor, UserActor) and session.user_id != actor.user_id:
            raise NotFoundError("Mock session not found")
        return await self._to_mock_response(session)

    async def log_question(
        self,
        profile_id: str,
        *,
        actor: UserActor,
        body: QuestionUpsertRequest,
    ) -> QuestionSummary:
        await self._profiles.get(profile_id, actor=actor)
        ctx = McpRunContext(db=self._db, user_id=actor.user_id, profile_id=profile_id)
        upserted = await question_upsert(
            ctx,
            stem=body.stem,
            question_type=body.question_type,
            company=body.company,
            role_title=body.role_title,
            job_id=body.job_id,
            mock_session_id=body.mock_session_id,
            round=body.round,
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
            raise NotFoundError("Question not found")
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
            bank_draw_count=draw_n,
            generated_count=int(session.generated_count or 0),
            questions=cards,
        )
