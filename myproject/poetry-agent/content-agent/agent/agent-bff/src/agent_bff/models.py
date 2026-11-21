"""Request/response models for Poetry Studio's BFF API (A-contract §7).

Vocabulary values mirror the Java host (``Vocabulary.java``). The v1 proposal schema is unchanged in
structure; only audience/certainty were aligned with Java, because a mismatch makes an approved
annotation fail at apply time.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_bff.instruction_guard import violation

ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{1,63}$"
ROLES = ("CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN")
REVIEW_ROLES = frozenset({"CONTENT_EDITOR", "HISTORICAL_REVIEWER"})
APPLY_ROLES = frozenset({"CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER"})
SOURCE_REVIEW_ROLES = frozenset({"HISTORICAL_REVIEWER", "PLATFORM_ADMIN"})

# Java Vocabulary.AUDIENCES / CERTAINTIES. Agents may not assert KNOWN (a human establishes that).
AUDIENCES = ("PRIMARY", "JUNIOR", "SENIOR")
JAVA_CERTAINTIES = ("KNOWN", "LIKELY", "DISPUTED", "UNKNOWN")
AGENT_CERTAINTIES = ("LIKELY", "DISPUTED", "UNKNOWN")
ANNOTATION_KINDS = ("WORD", "PHRASE", "ALLUSION", "IMAGE", "RHYME", "OTHER")


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_RUNTIME = "WAITING_FOR_RUNTIME"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProposalStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLY_PENDING = "APPLY_PENDING"
    APPLIED = "APPLIED"


class Actor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str = Field(min_length=1, max_length=128)
    role: Literal["CONTENT_EDITOR", "HISTORICAL_REVIEWER", "RELEASE_MANAGER", "PLATFORM_ADMIN"]


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,127}$")
    title: str = Field(min_length=3, max_length=200)
    task_type: Literal["GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"]
    actor: Actor | None = None  # claimed identity; checked against the session, required only when auth is off
    instructions: str = Field(min_length=1, max_length=8000)
    requested_profile: Literal["authoring"] = "authoring"

    @field_validator("instructions")
    @classmethod
    def no_control_request(cls, value: str) -> str:
        reason = violation(value)
        if reason:
            raise ValueError(reason)
        return value


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Only a downgrade is expressible: the editor may force the deterministic runtime, never DeerFlow.
    runtime: Literal["STUB"] | None = None


class Task(BaseModel):
    task_id: str
    work_id: str
    title: str
    task_type: str
    status: TaskStatus
    actor: Actor
    instructions: str
    requested_profile: str
    created_at: datetime
    updated_at: datetime | None = None
    active_run_id: str | None = None


class RunBudget(BaseModel):
    tool_calls: int | None = None
    max_tool_calls: int | None = None
    elapsed_s: float | None = None
    max_wall_s: float | None = None
    tokens: int | None = None
    max_tokens: int | None = None


class Run(BaseModel):
    run_id: str
    task_id: str
    mandate_id: str
    work_id: str | None = None
    status: TaskStatus
    runtime: Literal["DEERFLOW", "STUB"]
    profile_name: str
    profile_fingerprint: str
    created_at: datetime
    updated_at: datetime | None = None
    reason: str | None = None
    runtime_thread_id: str | None = None
    runtime_run_id: str | None = None
    budget: RunBudget | None = None


class RunEvent(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]


class AnnotationDraftPayload(BaseModel):
    """The sole executable v1 operation; Java validates it again and writes DRAFT rows only."""

    model_config = ConfigDict(extra="forbid")
    operation: Literal["CREATE_ANNOTATION"]
    id: str = Field(pattern=ID_PATTERN)
    version_id: str = Field(pattern=ID_PATTERN)
    line_seq: int = Field(ge=1)
    annotation_kind: Literal["WORD", "PHRASE", "ALLUSION", "IMAGE", "RHYME", "OTHER"]
    audience: Literal["PRIMARY", "JUNIOR", "SENIOR"]
    content: str = Field(min_length=1, max_length=8000)
    claim_id: str = Field(pattern=ID_PATTERN)
    claim_value: str = Field(min_length=1, max_length=8000)
    certainty: Literal["LIKELY", "DISPUTED", "UNKNOWN"]
    source_id: str | None = Field(default=None, pattern=ID_PATTERN)
    locator: None = None  # an agent never supplies a locator; a human reviewer fills it in later


class DraftChange(BaseModel):
    """One candidate change. No content mutation happens without human review and Java validation."""

    model_config = ConfigDict(extra="forbid")
    change_type: Literal["GAP_REPORT", "ANNOTATION", "BACKGROUND", "CLAIM", "SCRIPT"]
    target_ref: str | None = Field(default=None, max_length=256)
    body: str = Field(min_length=1, max_length=8000)
    classification: Literal["DRAFT", "INTERPRETATION", "UNKNOWN"]
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    draft_payload: AnnotationDraftPayload | None = None


class DraftProposalPayload(BaseModel):
    """Schema shared by the worker's proposal recording and the human review surfaces."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    status: Literal["DRAFT"] = "DRAFT"
    summary: str = Field(min_length=1, max_length=2000)
    changes: list[DraftChange] = Field(min_length=1, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=50)
    human_review_question: str = Field(min_length=1, max_length=2000)


class CreateProposalRequest(BaseModel):
    """Internal ingress used only by the agent runtime."""

    model_config = ConfigDict(extra="forbid")
    mandate_id: str = Field(pattern=r"^mandate_")
    proposal: DraftProposalPayload


class ItemDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_index: int = Field(ge=0, le=49)
    decision: Literal["APPROVE", "REJECT"]
    comment: str = Field(default="", max_length=2000)


class ReviewProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: Actor | None = None
    decision: Literal["APPROVE", "REJECT"]
    comment: str = Field(default="", max_length=4000)
    item_decisions: list[ItemDecision] | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def unique_items(self) -> ReviewProposalRequest:
        indexes = [item.item_index for item in self.item_decisions or []]
        if len(indexes) != len(set(indexes)):
            raise ValueError("item_decisions contains the same item_index more than once")
        return self


class ProposalItem(BaseModel):
    item_index: int
    decision: str
    reviewer: str | None = None
    comment: str | None = None
    created_at: datetime | None = None


class Proposal(BaseModel):
    proposal_id: str
    task_id: str
    run_id: str
    mandate_id: str
    work_id: str
    status: ProposalStatus
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    review_id: str | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None
    application_state: Literal["NOT_REQUESTED", "PENDING_DOMAIN_API", "APPLIED"] = "NOT_REQUESTED"
    items: list[ProposalItem] | None = None
    executable_count: int | None = None
    approved_executable_count: int | None = None
    # Set when the decision/application itself was committed but a follow-up write failed or was repaired:
    # RUN_STATE_NOT_UPDATED | EVENT_NOT_RECORDED | RECONCILED. Never an error: the content change is already safe.
    warnings: list[str] | None = None


class Review(BaseModel):
    review_id: str
    proposal_id: str
    actor: Actor
    decision: Literal["APPROVE", "REJECT"]
    comment: str
    created_at: datetime


class LocatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: Actor | None = None
    locator: str = Field(min_length=1, max_length=300)
    evidence_excerpt: str | None = Field(default=None, max_length=4000)
    note: str | None = Field(default=None, max_length=2000)


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: Actor | None = None
    decision: Literal["VERIFY", "REJECT"]
    note: str | None = Field(default=None, max_length=2000)
