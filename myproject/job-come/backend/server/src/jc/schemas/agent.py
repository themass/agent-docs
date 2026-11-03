"""Agent session API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from jc.agent.roles import default_role


class AgentSessionCreateRequest(BaseModel):
    profile_id: str | None = Field(default=None, description="Active profile to bind")
    job_id: str | None = Field(default=None, description="Bind job for interview prep context")
    role_id: str = Field(
        default_factory=lambda: default_role().id,
        description="The agent the session runs as: one of the entry roles in roles.yaml",
    )
    kind: str = Field(default="resume", description="resume | coach")


class AgentSessionResponse(BaseModel):
    id: str
    deerflow_thread_id: str
    role_id: str | None
    kind: str
    status: str
    profile_id: str | None
    created_at: datetime


class AgentSessionListItem(BaseModel):
    id: str
    role_id: str | None
    kind: str
    status: str
    profile_id: str | None
    title: str | None = Field(
        default=None,
        description="First user message snippet for session list display",
    )
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
    # Voice clips only. The browser does the speech-to-text (Web Speech API) and sends
    # both: the clip is the archive, the transcript is what the model reads. Stored on
    # the attachment rather than only inside `content`, so a replayed turn can still say
    # which words came out of which recording instead of leaving an orphan audio player.
    transcript: str | None = Field(
        default=None,
        max_length=4_000,
        description="Browser speech-to-text for an audio attachment",
    )
    duration_ms: int | None = Field(
        default=None,
        ge=0,
        le=6 * 60 * 60 * 1000,
        description="Recorded length of an audio attachment",
    )


class AgentUiFocus(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    kind: str = Field(default="experience", max_length=64)
    label: str = Field(default="", max_length=256)
    excerpt: str | None = Field(default=None, max_length=500)


class AgentUiContext(BaseModel):
    mock_session_id: str | None = Field(default=None, max_length=128)
    page: str = Field(default="resume-agent", max_length=64)
    step: str = Field(default="review", max_length=32)
    focus: AgentUiFocus | None = None
    #: What the user came here to do, when the page knows it. A switch rule in roles.yaml may
    #: read it (`intent_archive`); absent means the role's default skill.
    intent: Literal["archive"] | None = None


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
    #: User-edited values for a subset of the paths the model already proposed in
    #: `ProfilePatchConfirm.patch`. Never a path outside that set -- the model still
    #: decides *what* is up for confirmation (ADR-003: it proposes, the user disposes
    #: on exactly that), this only lets the user adjust *how it reads* before
    #: accepting. Ignored when `approved` is false. Merged over the stored proposal
    #: and re-validated through the same `apply_profile_patch` pipeline the original
    #: proposal went through -- an edit gets no less scrutiny than a model's own patch.
    edited_patch: dict[str, Any] | None = None


class AgentConfirmResponse(BaseModel):
    status: Literal["applied", "rejected"]
    confirm_id: str
    profile_id: str | None = None
    version: int | None = None
    #: True when `edited_patch` changed what was written relative to the original
    #: proposal. The UI uses this to say "已按你的修改保存" instead of "已应用" --
    #: different enough from the model's own proposal that silently calling it
    #: "applied" would misreport whose wording ended up on the page.
    edited: bool = False
