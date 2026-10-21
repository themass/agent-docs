"""Admin user directory API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminUserListItem(BaseModel):
    id: str
    email: str
    role: str
    status: str
    display_name: str | None = None
    email_verified: bool
    profile_count: int = 0
    session_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserListItem]
    total: int
    limit: int
    offset: int
    #: What the server actually sorted by, echoed so a clickable table header
    #: renders its arrow from the applied order rather than the requested one —
    #: a defaulted or rejected sort would otherwise mark the wrong column.
    sort_by: str
    sort_dir: str


class AdminUserProfileSummary(BaseModel):
    id: str
    status: str
    version: int
    locale: str
    contact_name: str | None = None
    summary_text: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AdminUserDetailResponse(AdminUserListItem):
    locale: str | None = None
    default_elevation_level: str | None = None
    profiles: list[AdminUserProfileSummary] = []
