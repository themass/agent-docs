"""Wire models. The response never carries a score, a grade or a verdict on the learner."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Step = Literal["read", "arrive", "meet", "return", "recite"]
Action = Literal[
    "rephrase", "hint", "ask_why", "open_layer", "basis", "recite_prompt", "decline", "evaluate_retell", "free_text",
]
Layer = Literal["SCENE", "CITY", "WORLD", "PERSON"]
Role = Literal["guide", "poet", "narrator"]
Badge = Literal["FACT", "INTERPRETATION", "DRAMATIZATION", "NONE"]
Source = Literal["script", "llm"]
DegradedReason = Literal["disabled", "unavailable", "timeout", "rejected", "budget"]

SAY_LIMIT = 120
RETELL_LIMIT = 400


class TurnArgs(BaseModel):
    layer: Layer | None = None
    line_seq: int | None = Field(default=None, ge=1, le=64)
    ref: str | None = Field(default=None, max_length=64)
    text: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def _bound_text(cls, value: object) -> object:
        # Truncate, never reject: a long sentence from a child is not an error. The hard cap also bounds
        # what any later stage could ever be handed.
        if isinstance(value, str):
            return value[:RETELL_LIMIT]
        return value


class TurnRequest(BaseModel):
    bundle_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    work_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    step: Step
    action: Action
    args: TurnArgs = Field(default_factory=TurnArgs)


class BasisItem(BaseModel):
    kind: Literal["script", "annotation"]
    id: str
    claim_id: str | None = None


class Supplement(BaseModel):
    point_id: str
    ask: str
    say: str
    badge: Badge = "NONE"
    basis: list[BasisItem] = Field(default_factory=list)


class Evaluation(BaseModel):
    """Which points were covered and which were not. There is deliberately no score field."""

    covered: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    covered_labels: list[str] = Field(default_factory=list)
    summary: str = ""
    supplement: list[Supplement] = Field(default_factory=list)


class TurnResponse(BaseModel):
    role: Role
    say: str
    basis: list[BasisItem] = Field(default_factory=list)
    badge: Badge = "NONE"
    next: str = "no_action"
    source: Source = "script"
    degraded_reason: DegradedReason | None = None
    evaluation: Evaluation | None = None
