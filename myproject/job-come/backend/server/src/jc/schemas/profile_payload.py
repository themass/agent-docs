"""Profile JSON payload — aligned with MVP §5.1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from jc.models.enums import ConfidenceLevel


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
    """A 项目经历 entry.

    `description` is the one-line overview of what the project was; `highlights` carries the
    accomplishments, one per entry, exactly like `ProfileExperience.highlights`. A project with
    several source bullets must keep them as several `highlights` entries — collapsing them into
    `description` loses content that no later step can recover.
    """

    id: str
    name: str
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.NEEDS_REVIEW


class EvidenceAnswer(BaseModel):
    """A fact the user supplied in answer to an evidence-gap question.

    These are **user-authored source facts**, not model output, which is why they are
    allowed to be used as support by the writer and accepted as support by the reviewer.
    They are kept separate from the bullet they relate to on purpose: rewriting the
    user's own bullet text is the writer's job at generation time, and silently editing
    a confirmed profile behind the user's back is exactly what the trust boundary
    forbids.
    """

    field_path: str = Field(description="所回答的要点路径，如 experiences[0].highlights[2]")
    question: str = Field(description="当时提出的问题，便于用户回看上下文")
    answer: str = Field(description="用户自己写的答案，视为真实事实")
    kind: str | None = Field(default=None, description="gap 类型，用于统计")
    answered_at: datetime | None = None


class ProfileConstraints(BaseModel):
    forbidden_companies: list[str] = Field(default_factory=list)
    forbidden_keywords: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)


class ProfilePreferences(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    salary_range: str | None = None
    remote_ok: bool = True
    role_family: str | None = Field(
        default=None,
        description=(
            "岗位族（role playbook）。为空时由标题推断；用户显式选择后以此为准，"
            "推断错误会导致整份简历按错误受众改写。"
        ),
    )
    framing_emphases: list[str] = Field(
        default_factory=list,
        description=(
            "包装角度（framing preset id），最多 2 个。决定每条要点先呈现哪一个"
            "已有事实；为空时按岗位族推荐值。不改变事实本身。"
        ),
    )


class ProfileMeta(BaseModel):
    source_file: str | None = None
    created_at: datetime | None = None
    confirmed_at: datetime | None = None
    ingest_mode: str | None = None
    extraction_source: str | None = None
    source_locale: str | None = None
    i18n_status: dict[str, str] = Field(default_factory=dict)


class ProfileI18nExperience(BaseModel):
    id: str
    title: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProfileI18nProject(BaseModel):
    id: str
    name: str | None = None
    role: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ProfileI18nEducation(BaseModel):
    id: str
    degree_line: str | None = None


class ProfileI18nPack(BaseModel):
    summary: str | None = None
    headline: str | None = None
    experiences: list[ProfileI18nExperience] = Field(default_factory=list)
    education: list[ProfileI18nEducation] = Field(default_factory=list)
    projects: list[ProfileI18nProject] = Field(default_factory=list)
    skills_line: str | None = None


class ProfilePayload(BaseModel):
    """Root document stored in jc_profile.payload."""

    contact: ProfileContact = Field(default_factory=ProfileContact)
    summary: str | None = None
    experiences: list[ProfileExperience] = Field(default_factory=list)
    education: list[ProfileEducation] = Field(default_factory=list)
    skills: list[ProfileSkill] = Field(default_factory=list)
    projects: list[ProfileProject] = Field(default_factory=list)
    evidence_answers: list[EvidenceAnswer] = Field(default_factory=list)
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
