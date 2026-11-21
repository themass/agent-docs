"""pydantic model of ``agent-output/1`` (contract section 6). Mirrors pipeline/contracts/agent-output.schema.json.

Vocabulary fields on ``annotation`` (kind/audience/certainty) are plain strings on purpose: a bad
value must surface as a *specific* validation rule (V4) rather than a generic type error.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnnotationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version_id: str = Field(min_length=1, max_length=64)
    line_seq: int = Field(strict=True)
    annotation_kind: str = Field(max_length=32)
    audience: str = Field(max_length=32)
    content: str = Field(min_length=1, max_length=20000)
    claim_value: str | None = Field(default=None, max_length=20000)
    certainty: str = Field(max_length=32)
    source_id: str | None = Field(default=None, max_length=64)
    locator: str | None = Field(default=None, max_length=1000)  # present only so it can be refused


class SourceRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_ref: str | None = Field(default=None, max_length=128)
    what_to_verify: str = Field(min_length=1, max_length=2000)
    suggested_source_kind: str | None = Field(default=None, max_length=32)
    suggested_source_title: str | None = Field(default=None, max_length=300)
    locator: str | None = Field(default=None, max_length=1000)  # present only so it can be refused


class OutputItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["GAP", "ANNOTATION", "BACKGROUND_NOTE", "SCRIPT_BEAT", "SOURCE_REQUEST", "TRIAGE_ITEM",
                 "REVIEW_FINDING"]
    epistemic: Literal["FACT_REQUEST", "INTERPRETATION", "DRAMATIZATION", "DRAFT_TEXT", "UNKNOWN"]
    target_ref: str | None = Field(default=None, max_length=256)
    body: str = Field(min_length=1, max_length=7000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    severity: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    annotation: AnnotationBody | None = None
    source_request: SourceRequestBody | None = None


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_id: Literal["agent-output/1"] = Field(alias="schema")
    task_type: Literal["GAP_ANALYSIS", "ANNOTATION_DRAFT", "SCRIPT_DRAFT", "COMPILE_TRIAGE", "CONTENT_REVIEW"]
    summary: str = Field(min_length=1, max_length=1500)
    items: list[OutputItem] = Field(default_factory=list, max_length=50)
    unknowns: list[str] = Field(default_factory=list, max_length=50)
    human_review_question: str = Field(min_length=1, max_length=2000)

    def to_json_dict(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")
