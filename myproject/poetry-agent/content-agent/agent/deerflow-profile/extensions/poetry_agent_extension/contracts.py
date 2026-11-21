"""Pure, reviewable contracts for the eventual DeerFlow extension package.

No DeerFlow SDK import is used here so policy checks can be exercised independently of a runtime.
Vocabularies mirror Java ``Vocabulary.java`` and A-contract section 6 (agent-output/1).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Java vocabulary (Vocabulary.java). An agent may never use KNOWN certainty.
AUDIENCES = ("PRIMARY", "JUNIOR", "SENIOR")
AGENT_CERTAINTIES = ("LIKELY", "DISPUTED", "UNKNOWN")
ANNOTATION_KINDS = ("WORD", "PHRASE", "ALLUSION", "IMAGE", "RHYME", "OTHER")
CLAIM_KINDS = ("FACT", "INTERPRETATION", "DRAMATIZATION")
LAYERS = ("SCENE", "CITY", "WORLD", "PERSON")

TASK_TYPES = ("GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW")
ITEM_KINDS = ("GAP", "ANNOTATION", "BACKGROUND_NOTE", "SCRIPT_BEAT", "SOURCE_REQUEST", "TRIAGE_ITEM",
              "REVIEW_FINDING")
EPISTEMICS = ("FACT_REQUEST", "INTERPRETATION", "DRAMATIZATION", "DRAFT_TEXT", "UNKNOWN")
SEVERITIES = ("HIGH", "MEDIUM", "LOW")
ACTOR_ROLES = ("CONTENT_EDITOR", "HISTORICAL_REVIEWER")

# Limits from A-contract section 6.
MAX_ITEMS = 50
MAX_UNKNOWNS = 50
MAX_SUMMARY_CHARS = 1500
MAX_BODY_CHARS = 7000
MAX_ANNOTATION_CHARS = 8000

# Substrings that may never appear in a tool allow-list (poetry-policy.yaml forbidden_capabilities).
BLOCKED_TOOL_WORDS = (
    "publish",
    "retract",
    "verify",
    "delete",
    "sql",
    "apply",
    "filesystem",
    "shell",
    "bash",
    "request_compile",
    "create_draft_proposal",
)


class Mandate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mandate_id: str = Field(default_factory=lambda: f"mandate_{uuid4().hex}")
    run_id: str = Field(pattern=r"^run_")
    work_id: str = Field(min_length=2, max_length=128)
    task_type: Literal["GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"]
    role: str
    actor_role: Literal["CONTENT_EDITOR", "HISTORICAL_REVIEWER"] = "CONTENT_EDITOR"
    idempotency_key: str = Field(min_length=12, max_length=128)
    allowed_tools: list[str]
    max_tool_calls: int = Field(ge=1, le=24)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("allowed_tools")
    @classmethod
    def prohibit_unsafe_tools(cls, tools: list[str]) -> list[str]:
        if any(any(word in tool.lower() for word in BLOCKED_TOOL_WORDS) for tool in tools):
            raise ValueError("unsafe tool cannot appear in a mandate")
        return tools


class AnnotationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str
    line_seq: int = Field(ge=1)
    annotation_kind: Literal["WORD", "PHRASE", "ALLUSION", "IMAGE", "RHYME", "OTHER"]
    audience: Literal["PRIMARY", "JUNIOR", "SENIOR"]
    content: str = Field(min_length=1, max_length=MAX_ANNOTATION_CHARS)
    claim_value: str | None = None
    certainty: Literal["LIKELY", "DISPUTED", "UNKNOWN"]  # KNOWN is not available to an agent
    source_id: str | None = None


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_ref: str | None = None
    what_to_verify: str = Field(min_length=1)
    suggested_source_kind: str | None = None
    suggested_source_title: str | None = None


class OutputItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["GAP", "ANNOTATION", "BACKGROUND_NOTE", "SCRIPT_BEAT", "SOURCE_REQUEST", "TRIAGE_ITEM",
                 "REVIEW_FINDING"]
    epistemic: Literal["FACT_REQUEST", "INTERPRETATION", "DRAMATIZATION", "DRAFT_TEXT", "UNKNOWN"]
    target_ref: str | None = None
    body: str = Field(min_length=1, max_length=MAX_BODY_CHARS)
    evidence_refs: list[str] = Field(default_factory=list)
    severity: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    annotation: AnnotationDraft | None = None
    source_request: SourceRequest | None = None

    @model_validator(mode="after")
    def fact_requests_carry_no_annotation(self) -> OutputItem:
        # A-contract section 6 rule 3: factual content is only ever a source request.
        if self.epistemic == "FACT_REQUEST" and self.annotation is not None:
            raise ValueError("a FACT_REQUEST item must not carry an annotation")
        return self


class AgentOutput(BaseModel):
    """agent-output/1: the single json fence in the agent's last message."""

    model_config = ConfigDict(extra="forbid")
    schema_: Literal["agent-output/1"] = Field(alias="schema")
    task_type: Literal["GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"]
    summary: str = Field(max_length=MAX_SUMMARY_CHARS)
    items: list[OutputItem] = Field(max_length=MAX_ITEMS)
    unknowns: list[str] = Field(default_factory=list, max_length=MAX_UNKNOWNS)
    human_review_question: str = Field(min_length=1)


class ProposalEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: str = Field(default_factory=lambda: f"proposal_{uuid4().hex}")
    mandate_id: str = Field(pattern=r"^mandate_")
    work_id: str
    status: str = "DRAFT"
    changes: list[dict[str, Any]]
    evidence_refs: list[str]
    unknowns: list[str]

    @field_validator("status")
    @classmethod
    def only_draft(cls, status: str) -> str:
        if status != "DRAFT":
            raise ValueError("extension proposals may only be DRAFT")
        return status

    @field_validator("changes")
    @classmethod
    def executable_payloads_follow_agent_vocabulary(cls, changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for change in changes:
            payload = change.get("draft_payload")
            if payload is None:
                continue
            if payload.get("locator") not in (None, ""):
                raise ValueError("an agent proposal may not supply a locator")
            if payload.get("audience") is not None and payload["audience"] not in AUDIENCES:
                raise ValueError("audience must be one of " + "|".join(AUDIENCES))
            if payload.get("certainty") is not None and payload["certainty"] not in AGENT_CERTAINTIES:
                raise ValueError("certainty from an agent must be one of " + "|".join(AGENT_CERTAINTIES))
        return changes
