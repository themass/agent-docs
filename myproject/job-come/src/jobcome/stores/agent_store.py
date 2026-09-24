"""Agent session persistence."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jobcome.models.agent import AgentSession
from jobcome.models.agent_message import AgentMessage


class AgentStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, session: AgentSession) -> AgentSession:
        self._db.add(session)
        await self._db.flush()
        return session

    async def get_by_id(self, session_id: str) -> AgentSession | None:
        return await self._db.get(AgentSession, session_id)

    async def get_by_thread(self, thread_id: str) -> AgentSession | None:
        stmt = select(AgentSession).where(AgentSession.deerflow_thread_id == thread_id).limit(1)
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        *,
        profile_id: str | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[AgentSession]:
        stmt = select(AgentSession).where(AgentSession.user_id == user_id)
        if profile_id:
            stmt = stmt.where(AgentSession.profile_id == profile_id)
        if kind:
            stmt = stmt.where(AgentSession.kind == kind)
        stmt = stmt.order_by(AgentSession.updated_at.desc()).limit(limit)
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
    ) -> tuple[list[AgentSession], int]:
        base = select(AgentSession)
        count_stmt = select(func.count()).select_from(AgentSession)
        if user_id:
            base = base.where(AgentSession.user_id == user_id)
            count_stmt = count_stmt.where(AgentSession.user_id == user_id)
        total = int((await self._db.execute(count_stmt)).scalar_one())
        stmt = base.order_by(AgentSession.updated_at.desc()).offset(offset).limit(limit)
        rows = list((await self._db.execute(stmt)).scalars().all())
        return rows, total

    async def message_counts(self, session_ids: list[str]) -> dict[str, int]:
        if not session_ids:
            return {}
        stmt = (
            select(AgentMessage.session_id, func.count())
            .where(AgentMessage.session_id.in_(session_ids))
            .group_by(AgentMessage.session_id)
        )
        rows = (await self._db.execute(stmt)).all()
        return {session_id: int(count) for session_id, count in rows}
