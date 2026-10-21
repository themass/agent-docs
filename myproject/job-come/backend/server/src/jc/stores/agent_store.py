"""Agent session persistence."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.agent import AgentSession
from jc.models.agent_message import AgentMessage
from jc.models.user import User
from jc.stores.sorting import SortSpec

#: Sortable columns for the admin session list. Keys are the API field names, so a
#: clickable table header passes its own key straight through (see
#: `jc.stores.sorting` for why the allow-list and the tiebreaker are not optional).
#: `message_count` is deliberately absent: it is computed per page by
#: `message_counts`, so sorting by it would order the page rather than the table and
#: show a different "busiest session" on every page.
SESSION_SORT = SortSpec(
    fields={
        "updated_at": AgentSession.updated_at,
        "created_at": AgentSession.created_at,
        "id": AgentSession.id,
        "user_id": AgentSession.user_id,
        "kind": AgentSession.kind,
        "status": AgentSession.status,
        "skill_hint": AgentSession.skill_hint,
    },
    default="updated_at",
    tiebreaker=AgentSession.id,
)


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
        search: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> tuple[list[AgentSession], int, str, str]:
        """Admin session listing. `search` matches session id, thread id, or the
        owning user's email — the three things an admin actually has in hand
        when chasing down one conversation (a support ticket quotes an email,
        a log line quotes a session or thread id).

        Returns the resolved `(sort_by, sort_dir)` alongside the rows so the
        response can tell the table which header to mark as sorted. Echoing the
        server's own answer rather than the request means a defaulted or
        normalised sort cannot render an arrow on the wrong column."""
        base = select(AgentSession)
        count_stmt = select(func.count()).select_from(AgentSession)
        if user_id:
            base = base.where(AgentSession.user_id == user_id)
            count_stmt = count_stmt.where(AgentSession.user_id == user_id)
        if search:
            pattern = f"%{search.lower()}%"
            condition = or_(
                AgentSession.id.like(pattern),
                AgentSession.deerflow_thread_id.like(pattern),
                User.email.like(pattern),
            )
            base = base.join(User, User.id == AgentSession.user_id).where(condition)
            count_stmt = count_stmt.join(User, User.id == AgentSession.user_id).where(condition)
        order_by, field, direction = SESSION_SORT.order_by(sort_by, sort_dir)
        total = int((await self._db.execute(count_stmt)).scalar_one())
        stmt = base.order_by(*order_by).offset(offset).limit(limit)
        rows = list((await self._db.execute(stmt)).scalars().all())
        return rows, total, field, direction

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

    async def session_counts_by_user(self, user_ids: list[str]) -> dict[str, int]:
        if not user_ids:
            return {}
        stmt = (
            select(AgentSession.user_id, func.count())
            .where(AgentSession.user_id.in_(user_ids))
            .group_by(AgentSession.user_id)
        )
        rows = (await self._db.execute(stmt)).all()
        return {user_id: int(count) for user_id, count in rows}
