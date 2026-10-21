"""Profile JSON payload — aligned with MVP §5.1."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from jc.models.enums import ConfidenceLevel
from jc.resume_locale import TRACK_BILINGUAL, TRACK_EN, normalize_track


class ProfileLink(BaseModel):
    type: str
    url: str


class ProfilePhoto(BaseModel):
    """The candidate's headshot, stored as an object-storage pointer plus a switch.

    `storage_key` is the durable record and `download_url` is a short-lived signed
    URL re-derived on read (same contract as `jc_agent_message` attachments) — a
    payload that persisted only the signed URL would render a broken image as soon
    as it expired.

    `enabled` defaults to False, so uploading a photo never silently changes what an
    export looks like: a resume gains a headshot only when the user asks for one.
    The flag is kept separate from `storage_key` rather than encoding "off" as a
    cleared key, because turning the photo off must not destroy the upload the user
    may turn back on in the next breath.
    """

    storage_key: str | None = None
    download_url: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    enabled: bool = False
    #: Whether the bilingual track draws the photo too. Separate from `enabled`
    #: because the switch means "show it on my Chinese resume", and a bilingual
    #: document is usually read by the English-market side of a hiring process,
    #: where a headshot is at best noise and in several jurisdictions something
    #: recruiters are instructed to discard. Defaulting it off means a user who
    #: turned the photo on for 中文 does not silently ship it abroad; opting in
    #: is one checkbox. The English-only track ignores both flags (see
    #: `renders_for_locale`), because there the answer is never.
    show_in_bilingual: bool = False

    @property
    def renderable(self) -> bool:
        """Whether an exporter *could* draw this photo — switch on and bytes stored.

        Locale is a separate question: see `renders_for_locale`, which is what the
        draft builder asks. This property stays locale-free so the editor preview and
        the profile API can report "the user has it on" without knowing which track
        is being exported.
        """
        return bool(self.enabled and self.storage_key)

    def renders_for_locale(self, locale: str | None) -> bool:
        """Whether this photo belongs on the resume for a given output track.

        The rule is per-market convention rather than per-user preference, so it
        lives here instead of being re-derived at each export site:

        * **zh-CN** — a headshot is standard on a Chinese resume, so the user's
          switch decides.
        * **en-US** — never. US/UK/EU screening guidance commonly tells recruiters
          to reject or redact resumes carrying a photo (bias exposure), so drawing
          one because a Chinese-track switch was on would actively damage the
          application. No flag overrides this; that is why it is not a setting.
        * **zh-en bilingual** — off unless explicitly opted in, because the reason
          a bilingual document exists is usually an English-reading audience.

        Returns False for an unrenderable photo regardless of track, so callers do
        not need to check `renderable` as well.
        """
        if not self.renderable:
            return False
        track = normalize_track(locale)
        if track == TRACK_EN:
            return False
        if track == TRACK_BILINGUAL:
            return self.show_in_bilingual
        return True


class ProfileContact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[ProfileLink] = Field(default_factory=list)
    # Lives on `contact` rather than at the payload root because a headshot is
    # identity material, read by the same masthead that renders name and contact
    # line -- keeping it here means one section owns everything that appears above
    # the first horizontal rule.
    photo: ProfilePhoto = Field(default_factory=ProfilePhoto)


class ProfileExperience(BaseModel):
    """One role. `highlights` carries the evidence; `scope` frames it.

    `scope` is the 先总后分 layer as a **source fact**: what the person owned and how big
    it was, in their own words. It is kept on the profile rather than derived at write
    time because it cannot be derived — a list of accomplishments does not reveal the
    team size, the budget, or the mandate behind them. Without it a reader has to infer
    scale from the bullets, which is the single most common reason a senior career reads
    as a mid-level one.
    """

    id: str
    company: str
    title: str
    start_date: str
    end_date: str | None = None
    location: str | None = None
    scope: str | None = Field(
        default=None,
        description="一句话说明这段经历里你负责的范围与量级，作为真实事实由用户提供。",
    )
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
    scope: str | None = Field(
        default=None,
        description="一句话说明项目的量级与你的角色，作为真实事实由用户提供。",
    )
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


class RetractedClaim(BaseModel):
    claim: str = Field(min_length=2, max_length=500)
    correction: str = Field(min_length=1, max_length=1000)
    scope: Literal["profile", "experience", "project"]
    entity_id: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_scope(self) -> RetractedClaim:
        if not self.claim.strip() or not self.correction.strip():
            raise ValueError("Claim and correction must not be blank")
        if self.scope == "profile" and self.entity_id is not None:
            raise ValueError("Profile-wide correction must not carry an entity_id")
        if self.scope != "profile" and not (self.entity_id or "").strip():
            raise ValueError("Entity-scoped correction requires a stable entity_id")
        return self


class ProfileConstraints(BaseModel):
    retracted_claims: list[RetractedClaim] = Field(default_factory=list, max_length=100)
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
    # Request-local projection of applied confirmations, keyed by stable entity ID.
    approved_resume_fields: dict[str, list[str]] = Field(default_factory=dict)
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
