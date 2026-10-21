"""Evidence-gap API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricCandidateItem(BaseModel):
    """A fillable way to quantify one bullet. Never carries a value -- see
    `services/metric_prompts`."""

    dimension: str
    unit: str = ""
    direction: str = "unknown"
    skeleton: str


class EvidenceGapItem(BaseModel):
    field_path: str
    kind: str
    source_text: str
    question: str
    examples: list[str] = Field(default_factory=list)
    weight: int
    #: Set when the user has already answered this exact question.
    answer: str | None = None
    #: Clickable metric skeletons, for the gap kinds whose answer is a figure. Empty for
    #: the kinds that ask for a sentence instead.
    metrics: list[MetricCandidateItem] = Field(default_factory=list)


class EvidenceGapsResponse(BaseModel):
    role_family: str
    role_label: str
    quantification_optional: bool
    gaps: list[EvidenceGapItem] = Field(default_factory=list)
    answered_count: int = 0
    #: Role families the user may switch to. Inference is a guess; the user decides.
    families: list[dict] = Field(default_factory=list)


class EvidenceAnswerInput(BaseModel):
    field_path: str
    question: str
    answer: str = Field(min_length=1, max_length=2000)
    kind: str | None = None


class EvidenceAnswerRequest(BaseModel):
    answers: list[EvidenceAnswerInput] = Field(default_factory=list, max_length=50)


class EvidenceAnswerResponse(BaseModel):
    profile_id: str
    version: int
    stored: int
    #: Resolved family, echoed so the client can refresh questions. Read-only here --
    #: the writing-options endpoint is the only writer.
    role_family: str
