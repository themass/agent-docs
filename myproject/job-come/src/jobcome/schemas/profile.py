"""Profile API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from jobcome.schemas.profile_payload import ProfilePayload


class ProfileSourceResponse(BaseModel):
    id: str
    file_name: str
    content_type: str | None
    file_size: int | None
    storage_key: str
    parse_status: str
    parse_error: str | None
    created_at: datetime


class ProfileResponse(BaseModel):
    id: str
    status: str
    version: int
    locale: str
    payload: ProfilePayload
    sources: list[ProfileSourceResponse]
    contact_name: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProfileUpdateRequest(BaseModel):
    payload: ProfilePayload = Field(description="完整档案 JSON（contact / experiences / education 等）")
    expected_version: int | None = Field(
        default=None,
        description="乐观锁：与当前 version 不一致时返回 409",
    )


class ProfileConfirmResponse(BaseModel):
    id: str
    status: str
    version: int
    confirmed_at: datetime


class ProfileListItem(BaseModel):
    id: str
    status: str
    contact_name: str | None
    summary_text: str | None
    updated_at: datetime
    is_active: bool = False


class ProfileListResponse(BaseModel):
    profiles: list[ProfileListItem]
    active_profile_id: str | None
