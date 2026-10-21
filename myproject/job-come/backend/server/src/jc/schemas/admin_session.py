"""Admin session audit API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AdminSessionListItem(BaseModel):
    id: str
    user_id: str
    #: Denormalised from the owning user so an audit row is readable without a second
    #: lookup. A session whose user was hard-deleted keeps the id and reports no name
    #: rather than dropping out of the audit list.
    user_display_name: str | None = None
    user_email: str | None = None
    profile_id: str | None
    job_id: str | None
    kind: str
    status: str
    skill_hint: str | None
    deerflow_thread_id: str
    trace_id: str | None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class AdminSessionListResponse(BaseModel):
    sessions: list[AdminSessionListItem]
    total: int
    limit: int
    offset: int
    #: What the server actually sorted by, echoed so a clickable table header
    #: renders its arrow from the applied order rather than the requested one —
    #: a defaulted or rejected sort would otherwise mark the wrong column.
    sort_by: str
    sort_dir: str


class AdminSessionDetailResponse(AdminSessionListItem):
    pass


class AdminTimelineTurn(BaseModel):
    turn_index: int
    user_message: str | None = None
    user_attachments: list[dict[str, Any]] = Field(default_factory=list)
    assistant_message: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class AdminTimelineResponse(BaseModel):
    session_id: str
    deerflow_thread_id: str
    turns: list[AdminTimelineTurn]
    raw_message_count: int


class AdminCheckpointMessage(BaseModel):
    index: int
    role: str
    content: str | list[Any] | dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_name: str | None = None
    tool_call_id: str | None = None
    additional_kwargs: dict[str, Any] = Field(default_factory=dict)
    usage_metadata: dict[str, Any] | None = None


class AdminCheckpointSummary(BaseModel):
    checkpoint_id: str
    parent_checkpoint_id: str | None
    ts: str | None
    message_count: int


class AdminCheckpointResponse(BaseModel):
    session_id: str
    deerflow_thread_id: str
    checkpoint_count: int
    latest_checkpoint_id: str | None
    summaries: list[AdminCheckpointSummary]
    messages: list[AdminCheckpointMessage]
    skill_context: dict[str, Any] = Field(default_factory=dict)
    thread_data: dict[str, Any] = Field(default_factory=dict)


class AdminMcpResourceInfo(BaseModel):
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


class AdminMcpServerInfo(BaseModel):
    name: str
    enabled: bool
    type: str | None = None
    description: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    resources: list[AdminMcpResourceInfo] = Field(default_factory=list)


class AdminToolInfo(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    registered_on_mcp_server: bool = False
    skills: list[str] = Field(default_factory=list)


class AdminSkillInfo(BaseModel):
    id: str
    enabled: bool
    description: str | None = None
    body_preview: str | None = None
    tools: list[str] = Field(default_factory=list)
    scope_for_hints: list[str] = Field(default_factory=list)


class AdminInventoryResponse(BaseModel):
    mcp_servers: list[AdminMcpServerInfo]
    middlewares: list[str]
    mcp_interceptors: list[str]
    tools: list[AdminToolInfo]
    skills: list[AdminSkillInfo]
    models: list[dict[str, Any]] = Field(default_factory=list)
    subagents: list[dict[str, Any]] = Field(default_factory=list)
    product_rules_preview: str | None = None


class AdminMessageItem(BaseModel):
    id: str
    session_id: str
    role: str
    event_type: str
    content: str | None = None
    payload: dict[str, Any] | None = None
    created_at: datetime


class AdminMessageListResponse(BaseModel):
    session_id: str
    messages: list[AdminMessageItem]
    total: int


class AdminTraceItem(BaseModel):
    id: str
    session_id: str
    seq: int
    user_id: str | None = None
    profile_id: str | None = None
    job_id: str | None = None
    mock_session_id: str | None = None
    trace_id: str | None = None
    llm_call_id: str | None = None
    event_type: str
    role: str
    payload: Any = None
    attachments: list[Any] | None = None
    created_at: datetime


class AdminTraceListResponse(BaseModel):
    session_id: str
    events: list[AdminTraceItem]
    total: int
