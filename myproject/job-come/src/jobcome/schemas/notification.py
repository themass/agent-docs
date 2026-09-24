"""In-app notification schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NotificationType = Literal[
    "system",
    "email_verify",
    "profile_action",
    "parse_quality",
    "merge_conflict",
    "export",
    "agent",
    "campaign",
]

NotificationPriority = Literal["low", "normal", "high", "critical"]

DismissPolicy = Literal[
    "manual",
    "on_read",
    "on_action",
    "auto_when_resolved",
]


class NotificationAction(BaseModel):
    label: str
    href: str | None = None
    action: str | None = None


class NotificationItem(BaseModel):
    id: str
    type: NotificationType
    priority: NotificationPriority = "normal"
    title: str
    body: str
    created_at: datetime
    read: bool = False
    dismissed: bool = False
    dismiss_policy: DismissPolicy = "on_read"
    action: NotificationAction | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int


class NotificationReadRequest(BaseModel):
    notification_ids: list[str] = Field(min_length=1)


class NotificationDismissRequest(BaseModel):
    notification_ids: list[str] = Field(min_length=1)
