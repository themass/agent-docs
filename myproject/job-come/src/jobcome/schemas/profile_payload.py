"""Profile JSON payload — aligned with MVP §5.1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from jobcome.models.enums import ConfidenceLevel


class ProfileLink(BaseModel):
    type: str
    url: str


class ProfileContact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[ProfileLink] = Field(default_factory=list)


class ProfileExperience(BaseModel):
    id: str
    company: str
    title: str
    start_date: str
    end_date: str | None = None
    location: str | None = None
    highlights: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.NEEDS_REVIEW


class ProfileEducation(BaseModel):
    id: str
    school: str
    degree: str | None = None
    major: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.NEEDS_REVIEW


class ProfileSkill(BaseModel):
    name: str
    level: str | None = None
    evidence: list[str] = Field(default_factory=list)


class ProfileProject(BaseModel):
    id: str
    name: str
    role: str | None = None
    description: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.NEEDS_REVIEW


class StarStory(BaseModel):
    id: str
    situation: str
    task: str
    action: str
    result: str
    tags: list[str] = Field(default_factory=list)


class ProfileConstraints(BaseModel):
    forbidden_companies: list[str] = Field(default_factory=list)
    forbidden_keywords: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)


class ProfilePreferences(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    salary_range: str | None = None
    remote_ok: bool = True


class ProfileMeta(BaseModel):
    source_file: str | None = None
    created_at: datetime | None = None
    confirmed_at: datetime | None = None
    ingest_mode: str | None = None
    source_locale: str | None = None
    i18n_status: dict[str, str] = Field(default_factory=dict)


class ProfileI18nExperience(BaseModel):
    id: str
    title: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProfileI18nEducation(BaseModel):
    id: str
    degree_line: str | None = None


class ProfileI18nPack(BaseModel):
    summary: str | None = None
    headline: str | None = None
    experiences: list[ProfileI18nExperience] = Field(default_factory=list)
    education: list[ProfileI18nEducation] = Field(default_factory=list)
    skills_line: str | None = None


class ProfilePayload(BaseModel):
    """Root document stored in jc_profile.payload."""

    contact: ProfileContact = Field(default_factory=ProfileContact)
    summary: str | None = None
    experiences: list[ProfileExperience] = Field(default_factory=list)
    education: list[ProfileEducation] = Field(default_factory=list)
    skills: list[ProfileSkill] = Field(default_factory=list)
    projects: list[ProfileProject] = Field(default_factory=list)
    star_stories: list[StarStory] = Field(default_factory=list)
    constraints: ProfileConstraints = Field(default_factory=ProfileConstraints)
    preferences: ProfilePreferences = Field(default_factory=ProfilePreferences)
    meta: ProfileMeta = Field(default_factory=ProfileMeta)
    i18n: dict[str, ProfileI18nPack] = Field(default_factory=dict)


class ElevationMapEntry(BaseModel):
    field_path: str
    source_text: str
    written_text: str
    needs_defense: bool = False


class CoachFeedback(BaseModel):
    score: int | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    defense_flags: list[str] = Field(default_factory=list)


class JobRequirements(BaseModel):
    skills: list[str] = Field(default_factory=list)
    years_min: int | None = None
    education: str | None = None
    keywords: list[str] = Field(default_factory=list)


class JobFit(BaseModel):
    score: int
    recommendation: Literal["go", "caution", "no"]
    gaps: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class CampaignProgress(BaseModel):
    real_interviews: int = 0
    real_interviews_required: int = 3
    mock_sessions: int = 0
    mock_sessions_required: int = 5
    bank_question_count: int = 0


class NotifyEmailPrefs(BaseModel):
    product_updates: bool = False
    security_alerts: bool = True
