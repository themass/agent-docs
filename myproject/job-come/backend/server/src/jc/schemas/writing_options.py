"""Writing-options schemas: the levers the user has over how their resume is written.

These are *presentation* preferences. Nothing here can add a fact to the profile, so the
endpoint is safe to be a plain user-controlled setter — unlike evidence answers, which
are source facts, and unlike profile patches, which require explicit confirmation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RoleFamilyOption(BaseModel):
    id: str
    label: str
    outcome_metrics: list[str] = Field(default_factory=list)
    must_haves: list[str] = Field(default_factory=list)
    quantification_optional: bool = False


class FramingPresetOption(BaseModel):
    id: str
    label: str
    hint: str
    #: True when this angle is what a recruiter in the resolved family reads for first.
    recommended: bool = False


class WritingOptionsResponse(BaseModel):
    #: Family actually in force, after override > job category > title inference.
    role_family: str
    role_label: str
    #: True when the family came from the user's explicit choice rather than inference.
    role_family_explicit: bool = False
    quantification_optional: bool = False
    #: Angles in force, strongest first. Never empty: falls back to the role default.
    framing_emphases: list[str] = Field(default_factory=list)
    #: True when the angles came from the user rather than the role default.
    framing_explicit: bool = False
    max_emphases: int = 2
    families: list[RoleFamilyOption] = Field(default_factory=list)
    presets: list[FramingPresetOption] = Field(default_factory=list)


class WritingOptionsRequest(BaseModel):
    #: Omit to leave unchanged; empty string clears the override back to inference.
    role_family: str | None = None
    #: Omit to leave unchanged; empty list clears back to the role default.
    framing_emphases: list[str] | None = Field(default=None, max_length=4)
