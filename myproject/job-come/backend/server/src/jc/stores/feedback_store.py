"""Feedback thread + message persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.feedback import FeedbackMessage, FeedbackThread
from jc.stores.sorting import SortSpec

#: Sortable columns for the admin feedback inbox. `created_at` matters as much as
#: `last_message_at` here: the triage question is "what has been waiting longest",
#: which is the filing time, while the default order answers "what moved most
#: recently".
FEEDBACK_SORT = SortSpec(
    fields={
        "last_message_at": FeedbackThread.last_message_at,
        "created_at": FeedbackThread.created_at,
        "message_count": FeedbackThread.message_count,
        "status": FeedbackThread.status,
        "category": FeedbackThread.category,
        "title": FeedbackThread.title,
        "last_message_role": FeedbackThread.last_message_role,
        "user_id": FeedbackThread.user_id,
    },
    default="last_message_at",
    tiebreaker=FeedbackThread.id,
)


class FeedbackStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # --- threads ---------------------------------------------------------

    async def create_thread(self, row: FeedbackThread) -> FeedbackThread:
        self._db.add(row)
        await self._db.flush()
        return row

    async def get_thread(self, thread_id: str) -> FeedbackThread | None:
        return await self._db.get(FeedbackThread, thread_id)

    async def list_for_user(self, user_id: str, *, limit: int = 100) -> list[FeedbackThread]:
        stmt = (
            select(FeedbackThread)
            .where(FeedbackThread.user_id == user_id)
            .order_by(FeedbackThread.last_message_at.desc())
            .limit(limit)
        )
        return list((await self._db.execute(stmt)).scalars().all())

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> tuple[list[FeedbackThread], int, str, str]:
        """Returns `(rows, total, resolved_sort_by, resolved_sort_dir)`."""
        base = select(FeedbackThread)
        if status:
            base = base.where(FeedbackThread.status == status)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = int((await self._db.execute(count_stmt)).scalar_one())

        order_by, field, direction = FEEDBACK_SORT.order_by(sort_by, sort_dir)
        stmt = base.order_by(*order_by).limit(limit).offset(offset)
        rows = list((await self._db.execute(stmt)).scalars().all())
        return rows, total, field, direction

    async def touch_thread(
        self,
        thread: FeedbackThread,
        *,
        last_message_role: str,
        last_message_at: datetime,
        status: str | None = None,
    ) -> FeedbackThread:
        thread.last_message_role = last_message_role
        thread.last_message_at = last_message_at
        thread.message_count += 1
        if status is not None:
            thread.status = status
        await self._db.flush()
        return thread

    async def set_status(self, thread: FeedbackThread, status: str) -> FeedbackThread:
        thread.status = status
        await self._db.flush()
        return thread

    # --- messages ----------------------------------------------------------

    async def add_message(self, row: FeedbackMessage) -> FeedbackMessage:
        self._db.add(row)
        await self._db.flush()
        return row

    async def list_messages(self, thread_id: str) -> list[FeedbackMessage]:
        stmt = (
            select(FeedbackMessage)
            .where(FeedbackMessage.thread_id == thread_id)
            .order_by(FeedbackMessage.created_at.asc())
        )
        return list((await self._db.execute(stmt)).scalars().all())
