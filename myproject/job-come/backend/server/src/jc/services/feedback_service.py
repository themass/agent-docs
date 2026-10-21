"""Feedback inbox — user submissions, admin replies, thread lifecycle.

Lifecycle rules (deliberately simple, not configurable):

- A user message always nudges a `resolved`/`closed` thread back to `open`.
  Otherwise a follow-up question from the user would land in a thread the
  admin list no longer surfaces as needing attention.
- An admin reply always sets the thread to `replying`. Admins change status
  explicitly (via the status endpoint) when they want `resolved`/`closed`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import AppError, NotFoundError
from jc.models.enums import FeedbackCategory, FeedbackMessageRole, FeedbackStatus
from jc.models.feedback import FeedbackMessage, FeedbackThread
from jc.models.user import User
from jc.schemas.admin_feedback import (
    AdminFeedbackThreadDetailResponse,
    AdminFeedbackThreadItem,
    AdminFeedbackThreadListResponse,
)
from jc.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackMessageItem,
    FeedbackReplyRequest,
    FeedbackThreadDetailResponse,
    FeedbackThreadItem,
    FeedbackThreadListResponse,
)
from jc.stores.feedback_store import FeedbackStore
from jc.stores.user_store import UserStore

# Threads in these statuses are considered "settled"; a new user message
# reopens them. Anything else (open/replying) is left as-is.
_REOPEN_ON_USER_MESSAGE = {FeedbackStatus.RESOLVED, FeedbackStatus.CLOSED}


def _message_item(row: FeedbackMessage) -> FeedbackMessageItem:
    return FeedbackMessageItem(
        id=row.id,
        role=row.role,
        body=row.body,
        created_at=row.created_at,
    )


def _thread_item(row: FeedbackThread) -> FeedbackThreadItem:
    return FeedbackThreadItem(
        id=row.id,
        title=row.title,
        category=row.category,
        status=row.status,
        last_message_role=row.last_message_role,
        last_message_at=row.last_message_at,
        message_count=row.message_count,
        created_at=row.created_at,
    )


def _admin_thread_item(row: FeedbackThread, user: User | None) -> AdminFeedbackThreadItem:
    return AdminFeedbackThreadItem(
        id=row.id,
        user_id=row.user_id,
        user_email=user.email if user else "(已删除用户)",
        user_display_name=user.meta.display_name if user and user.meta else None,
        title=row.title,
        category=row.category,
        status=row.status,
        last_message_role=row.last_message_role,
        last_message_at=row.last_message_at,
        message_count=row.message_count,
        created_at=row.created_at,
    )


class FeedbackService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._feedback = FeedbackStore(db)
        self._users = UserStore(db)

    # --- user-facing -------------------------------------------------------

    async def create_thread(
        self, *, user_id: str, body: FeedbackCreateRequest
    ) -> FeedbackThreadDetailResponse:
        if body.category not in set(FeedbackCategory):
            raise AppError("反馈分类不合法。", code="invalid_request")
        now = datetime.now(UTC)
        thread = await self._feedback.create_thread(
            FeedbackThread(
                id=new_id("fbt"),
                user_id=user_id,
                title=body.title,
                category=body.category,
                status=FeedbackStatus.OPEN,
                last_message_role=FeedbackMessageRole.USER,
                last_message_at=now,
                message_count=1,
            )
        )
        message = await self._feedback.add_message(
            FeedbackMessage(
                id=new_id("fbm"),
                thread_id=thread.id,
                role=FeedbackMessageRole.USER,
                author_user_id=user_id,
                body=body.body,
            )
        )
        await self._db.commit()
        return FeedbackThreadDetailResponse(
            **_thread_item(thread).model_dump(), messages=[_message_item(message)]
        )

    async def list_for_user(self, *, user_id: str) -> FeedbackThreadListResponse:
        rows = await self._feedback.list_for_user(user_id)
        return FeedbackThreadListResponse(threads=[_thread_item(r) for r in rows])

    async def get_for_user(
        self, *, user_id: str, thread_id: str
    ) -> FeedbackThreadDetailResponse:
        thread = await self._require_owned_thread(user_id=user_id, thread_id=thread_id)
        messages = await self._feedback.list_messages(thread_id)
        return FeedbackThreadDetailResponse(
            **_thread_item(thread).model_dump(),
            messages=[_message_item(m) for m in messages],
        )

    async def add_user_message(
        self, *, user_id: str, thread_id: str, body: FeedbackReplyRequest
    ) -> FeedbackThreadDetailResponse:
        thread = await self._require_owned_thread(user_id=user_id, thread_id=thread_id)
        now = datetime.now(UTC)
        await self._feedback.add_message(
            FeedbackMessage(
                id=new_id("fbm"),
                thread_id=thread.id,
                role=FeedbackMessageRole.USER,
                author_user_id=user_id,
                body=body.body,
            )
        )
        next_status = (
            FeedbackStatus.OPEN if thread.status in _REOPEN_ON_USER_MESSAGE else None
        )
        await self._feedback.touch_thread(
            thread,
            last_message_role=FeedbackMessageRole.USER,
            last_message_at=now,
            status=next_status,
        )
        await self._db.commit()
        messages = await self._feedback.list_messages(thread_id)
        return FeedbackThreadDetailResponse(
            **_thread_item(thread).model_dump(),
            messages=[_message_item(m) for m in messages],
        )

    async def _require_owned_thread(self, *, user_id: str, thread_id: str) -> FeedbackThread:
        thread = await self._feedback.get_thread(thread_id)
        # A thread that exists but belongs to someone else looks identical to
        # a missing one from the caller's point of view — don't leak existence.
        if thread is None or thread.user_id != user_id:
            raise NotFoundError("反馈记录不存在或已删除。", code="feedback_not_found")
        return thread

    # --- admin ---------------------------------------------------------------

    async def admin_list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        sort_by: str | None = None,
        sort_dir: str | None = None,
    ) -> AdminFeedbackThreadListResponse:
        rows, total, sorted_by, sorted_dir = await self._feedback.list_all(
            limit=min(limit, 200),
            offset=offset,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        users = await self._users.get_by_ids([r.user_id for r in rows])
        threads = [_admin_thread_item(r, users.get(r.user_id)) for r in rows]
        return AdminFeedbackThreadListResponse(
            threads=threads,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=sorted_by,
            sort_dir=sorted_dir,
        )

    async def admin_get(self, *, thread_id: str) -> AdminFeedbackThreadDetailResponse:
        thread = await self._require_thread(thread_id)
        user = (await self._users.get_by_ids([thread.user_id])).get(thread.user_id)
        messages = await self._feedback.list_messages(thread_id)
        return AdminFeedbackThreadDetailResponse(
            **_admin_thread_item(thread, user).model_dump(),
            messages=[_message_item(m) for m in messages],
        )

    async def admin_reply(
        self, *, admin_user_id: str, thread_id: str, body: str
    ) -> AdminFeedbackThreadDetailResponse:
        thread = await self._require_thread(thread_id)
        now = datetime.now(UTC)
        await self._feedback.add_message(
            FeedbackMessage(
                id=new_id("fbm"),
                thread_id=thread.id,
                role=FeedbackMessageRole.ADMIN,
                author_user_id=admin_user_id,
                body=body,
            )
        )
        await self._feedback.touch_thread(
            thread,
            last_message_role=FeedbackMessageRole.ADMIN,
            last_message_at=now,
            status=FeedbackStatus.REPLYING,
        )
        await self._db.commit()
        return await self.admin_get(thread_id=thread_id)

    async def admin_set_status(
        self, *, thread_id: str, status: str
    ) -> AdminFeedbackThreadDetailResponse:
        if status not in set(FeedbackStatus):
            raise AppError("反馈状态不合法。", code="invalid_request")
        thread = await self._require_thread(thread_id)
        await self._feedback.set_status(thread, status)
        await self._db.commit()
        return await self.admin_get(thread_id=thread_id)

    async def _require_thread(self, thread_id: str) -> FeedbackThread:
        thread = await self._feedback.get_thread(thread_id)
        if thread is None:
            raise NotFoundError("反馈记录不存在或已删除。", code="feedback_not_found")
        return thread
