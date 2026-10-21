"""Profile API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from jc.schemas.profile_payload import ProfilePayload


class ProfileSourceResponse(BaseModel):
    id: str
    file_name: str
    content_type: str | None
    file_size: int | None
    storage_key: str
    parse_status: str
    parse_phase: str | None = None
    parse_error: str | None
    created_at: datetime
    updated_at: datetime


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


class ProfileTextIngestRequest(BaseModel):
    """Pasted or typed resume content.

    The bounds are repeated in `ProfileIngestService.validate_text`, which is the
    authority: pydantic refuses the request with a generic validation error, while the
    service can say *why* in the user's language. Keeping both means a malformed API
    call is cheap to reject and a real user gets a sentence they can act on.
    """

    raw_text: str = Field(
        min_length=1,
        max_length=50_000,
        description="简历原文或一段自述（至少 80 字）",
    )
    title: str | None = Field(
        default=None,
        max_length=80,
        description="这段内容的名字，用于在来源列表里识别；留空即「粘贴的内容」",
    )


class ProfileUpdateRequest(BaseModel):
    payload: ProfilePayload = Field(
        description="完整档案 JSON（contact / experiences / education 等）"
    )
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
