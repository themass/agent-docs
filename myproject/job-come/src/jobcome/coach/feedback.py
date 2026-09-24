"""Structured coach feedback (five dimensions)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

_RUBRIC_PATH = (
    Path(__file__).resolve().parents[3] / "prompts" / "coach" / "mock_rubric_five_dims.md"
)

DIMENSION_KEYS = ("structure", "relevance", "depth", "communication", "reflection")


class CoachDimensionScores(BaseModel):
    structure: int = Field(ge=1, le=10)
    relevance: int = Field(ge=1, le=10)
    depth: int = Field(ge=1, le=10)
    communication: int = Field(ge=1, le=10)
    reflection: int = Field(ge=1, le=10)


class CoachFeedbackPayload(BaseModel):
    score: int = Field(ge=1, le=10)
    dimensions: CoachDimensionScores
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    rewrite_hint: str | None = None

    @field_validator("score", mode="before")
    @classmethod
    def _coerce_score(cls, value: Any) -> Any:
        if isinstance(value, float):
            return int(round(value))
        return value


def load_mock_rubric_markdown() -> str:
    if _RUBRIC_PATH.is_file():
        return _RUBRIC_PATH.read_text(encoding="utf-8")
    return "Five-dimension mock interview rubric."


def normalize_coach_feedback(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize agent-provided feedback; soft-fail to passthrough extras."""
    if not raw:
        return {}
    data = dict(raw)
    try:
        payload = CoachFeedbackPayload.model_validate(data)
        out = payload.model_dump(mode="json")
        for key, value in data.items():
            if key not in out:
                out[key] = value
        return out
    except Exception:  # noqa: BLE001
        dims = data.get("dimensions")
        if isinstance(dims, dict):
            score = data.get("score")
            if score is None and dims:
                vals = [dims.get(k) for k in DIMENSION_KEYS if isinstance(dims.get(k), (int, float))]
                if vals:
                    data["score"] = int(round(sum(vals) / len(vals)))
        return data


def overall_from_dimensions(dimensions: dict[str, Any]) -> int | None:
    vals = [dimensions.get(k) for k in DIMENSION_KEYS if isinstance(dimensions.get(k), (int, float))]
    if not vals:
        return None
    return int(round(sum(vals) / len(vals)))
