"""Admin feedback inbox API schemas.

Mirrors `jc.schemas.feedback` field-for-field (same transcript, two
viewpoints) plus the identity columns an admin list needs to triage without
opening every thread: who filed it and how many threads that person has
open.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from jc.schemas.feedback import FeedbackMessageItem


class AdminFeedbackThreadItem(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_display_name: str | None = None
    title: str
    category: str
    status: str
    last_message_role: str
    last_message_at: datetime
    message_count: int
    created_at: datetime


class AdminFeedbackThreadListResponse(BaseModel):
    threads: list[AdminFeedbackThreadItem]
    total: int
    limit: int
    offset: int
    #: What the server actually sorted by, echoed so a clickable table header
    #: renders its arrow from the applied order rather than the requested one —
    #: a defaulted or rejected sort would otherwise mark the wrong column.
    sort_by: str
    sort_dir: str


class AdminFeedbackThreadDetailResponse(AdminFeedbackThreadItem):
    messages: list[FeedbackMessageItem] = []


class AdminFeedbackReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class AdminFeedbackStatusRequest(BaseModel):
    status: str
