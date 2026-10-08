"""Interview persistence."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.interview import AnswerAttempt, InterviewQuestion, InterviewRecord, MockSession


class InterviewStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search_questions(
        self,
        profile_id: str,
        *,
        query: str = "",
        company: str | None = None,
        job_id: str | None = None,
        limit: int = 10,
    ) -> list[InterviewQuestion]:
        stmt = select(InterviewQuestion).where(InterviewQuestion.profile_id == profile_id)
        if company:
            stmt = stmt.where(InterviewQuestion.company == company)
        if job_id:
            stmt = stmt.where(InterviewQuestion.job_id == job_id)
        if query.strip():
            like = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    InterviewQuestion.stem.like(like),
                    InterviewQuestion.company.like(like),
                )
            )
        stmt = stmt.order_by(InterviewQuestion.updated_at.desc()).limit(limit)
        return list((await self._db.execute(stmt)).scalars().all())

    async def get_question(self, question_id: str) -> InterviewQuestion | None:
        return await self._db.get(InterviewQuestion, question_id)

    async def create_interview(self, record: InterviewRecord) -> InterviewRecord:
        self._db.add(record)
        await self._db.flush()
        return record

    async def add_attempt(self, attempt: AnswerAttempt) -> AnswerAttempt:
        self._db.add(attempt)
        await self._db.flush()
        return attempt

    async def create_question(self, question: InterviewQuestion) -> InterviewQuestion:
        self._db.add(question)
        await self._db.flush()
        return question

    async def find_question_by_stem(
        self,
        profile_id: str,
        stem: str,
        *,
        company: str | None = None,
    ) -> InterviewQuestion | None:
        stmt = select(InterviewQuestion).where(
            InterviewQuestion.profile_id == profile_id,
            InterviewQuestion.stem == stem.strip(),
        )
        if company:
            stmt = stmt.where(InterviewQuestion.company == company)
        stmt = stmt.limit(1)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def get_attempt(self, attempt_id: str) -> AnswerAttempt | None:
        return await self._db.get(AnswerAttempt, attempt_id)

    async def list_attempts_for_question(
        self, question_id: str, *, limit: int = 50
    ) -> list[AnswerAttempt]:
        stmt = (
            select(AnswerAttempt)
            .where(AnswerAttempt.question_id == question_id)
            .order_by(AnswerAttempt.created_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def count_questions(self, profile_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(InterviewQuestion)
            .where(InterviewQuestion.profile_id == profile_id)
        )
        return int((await self._db.execute(stmt)).scalar_one())

    async def create_mock_session(self, session: MockSession) -> MockSession:
        self._db.add(session)
        await self._db.flush()
        return session

    async def get_active_mock(
        self,
        profile_id: str,
        *,
        job_id: str | None = None,
    ) -> MockSession | None:
        stmt = select(MockSession).where(
            MockSession.profile_id == profile_id,
            MockSession.status == "active",
        )
        if job_id:
            stmt = stmt.where(MockSession.job_id == job_id)
        stmt = stmt.order_by(MockSession.started_at.desc()).limit(1)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_mock_sessions(self, profile_id: str, *, limit: int = 20) -> list[MockSession]:
        stmt = (
            select(MockSession)
            .where(MockSession.profile_id == profile_id)
            .order_by(MockSession.started_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())
