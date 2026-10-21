"""User-facing feedback inbox API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackMessageItem(BaseModel):
    id: str
    role: str
    body: str
    created_at: datetime


class FeedbackThreadItem(BaseModel):
    id: str
    title: str
    category: str
    status: str
    last_message_role: str
    last_message_at: datetime
    message_count: int
    created_at: datetime


class FeedbackThreadListResponse(BaseModel):
    threads: list[FeedbackThreadItem]


class FeedbackThreadDetailResponse(FeedbackThreadItem):
    messages: list[FeedbackMessageItem] = []


class FeedbackCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(default="other")
    body: str = Field(min_length=1, max_length=8000)


class FeedbackReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
