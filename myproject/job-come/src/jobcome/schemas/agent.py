"""Agent session API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AgentSessionCreateRequest(BaseModel):
    profile_id: str | None = Field(default=None, description="Active profile to bind")
    job_id: str | None = Field(default=None, description="Bind job for interview prep context")
    skill_hint: str = Field(default="resume-coach", description="Skill id under skills/public/")
    kind: str = Field(default="resume", description="resume | coach")


class AgentSessionResponse(BaseModel):
    id: str
    deerflow_thread_id: str
    skill_hint: str | None
    kind: str
    status: str
    profile_id: str | None
    created_at: datetime


class AgentSessionListItem(BaseModel):
    id: str
    skill_hint: str | None
    kind: str
    status: str
    profile_id: str | None
    created_at: datetime
    updated_at: datetime


class AgentSessionListResponse(BaseModel):
    sessions: list[AgentSessionListItem]


class AgentAttachment(BaseModel):
    kind: Literal["image", "file", "audio"] = "file"
    name: str = Field(min_length=1, max_length=256)
    label: str | None = Field(default=None, max_length=128)
    mime_type: str | None = None
    data_url: str | None = Field(default=None, description="Base64 data URL for images/audio")
    text_preview: str | None = Field(default=None, description="Extracted text for documents")


class AgentUiFocus(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    kind: str = Field(default="experience", max_length=64)
    label: str = Field(default="", max_length=256)
    excerpt: str | None = Field(default=None, max_length=500)


class AgentUiContext(BaseModel):
    page: str = Field(default="resume-agent", max_length=64)
    step: str = Field(default="review", max_length=32)
    focus: AgentUiFocus | None = None


class AgentMessageRequest(BaseModel):
    content: str = Field(default="", max_length=16_000)
    attachments: list[AgentAttachment] = Field(default_factory=list)
    reply_locale: str = Field(default="zh-CN", description="zh-CN | en-US；模型回复语言")
    ui_context: AgentUiContext | None = Field(
        default=None,
        description="前端当前页/步骤/选中字段 path，用于定位「这块」",
    )

    @model_validator(mode="after")
    def _require_content_or_attachments(self) -> AgentMessageRequest:
        if not self.content.strip() and not self.attachments:
            raise ValueError("content or attachments required")
        return self


class AgentMessageRecord(BaseModel):
    id: str
    session_id: str
    role: str
    event_type: str
    content: str | None
    payload: dict[str, Any] | None
    created_at: datetime


class AgentMessageListResponse(BaseModel):
    session_id: str
    messages: list[AgentMessageRecord]


class AgentConfirmRequest(BaseModel):
    confirm_id: str = Field(min_length=8, max_length=64)
    approved: bool = True


class AgentConfirmResponse(BaseModel):
    status: Literal["applied", "rejected"]
    confirm_id: str
    profile_id: str | None = None
    version: int | None = None
