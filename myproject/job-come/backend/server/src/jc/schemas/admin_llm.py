"""Admin LLM audit log API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AdminLlmAttempt(BaseModel):
    attempt_index: int
    model: str
    provider: str | None = None
    api_base_env: str | None = None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    validator_failed: bool = False
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_micro_usd: int | None = None


class AdminLlmCallItem(BaseModel):
    id: str
    user_id: str | None = None
    #: Denormalised from the owning user, same contract as the session audit list: the
    #: row stays readable without a per-row lookup, and a call made by no user (system
    #: scenarios) or by a hard-deleted one simply reports no name.
    user_display_name: str | None = None
    user_email: str | None = None
    actor_kind: str | None = None
    profile_id: str | None = None
    job_id: str | None = None
    session_id: str | None = None
    scenario: str
    caller: str
    channel: str
    skill_hint: str | None = None
    status: str
    final_model: str | None = None
    final_provider: str | None = None
    attempt_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_micro_usd: int | None = None
    trace_id: str | None = None
    stream: bool = False
    payload_truncated: bool = False
    created_at: datetime


class AdminLlmCallListResponse(BaseModel):
    calls: list[AdminLlmCallItem]
    total: int
    limit: int
    offset: int
    #: What the server actually sorted by, echoed so a clickable table header
    #: renders its arrow from the applied order rather than the requested one —
    #: a defaulted or rejected sort would otherwise mark the wrong column.
    sort_by: str
    sort_dir: str


class AdminLlmCallDetailResponse(AdminLlmCallItem):
    attempts: list[AdminLlmAttempt] = Field(default_factory=list)
    # Present only when JC_LLM_LOG_PAYLOAD is on. These carry resume content.
    prompt_text: str | None = None
    response_text: str | None = None
    reasoning_text: str | None = None


class AdminLlmUsageRow(BaseModel):
    key: str | None = None
    calls: int
    failed: int
    total_tokens: int
    cost_micro_usd: int
    avg_latency_ms: int


class AdminLlmUsageResponse(BaseModel):
    group_by: str
    days: int
    rows: list[AdminLlmUsageRow]
