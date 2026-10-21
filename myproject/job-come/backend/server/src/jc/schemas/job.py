"""JD parsing schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, StrictBool


class JDParseResult(BaseModel):
    integrity: dict = Field(default_factory=dict, description="服务端 JD 正文安全诊断；非安全保证")
    company: str | None = None
    role_title: str
    location: str | None = None
    employment_type: Literal["full_time", "contract", "intern"] | None = None
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    seniority: Literal["junior", "mid", "senior", "lead"] | None = None


class JobParseRequest(BaseModel):
    raw_text: str = Field(min_length=20, max_length=50_000)
    source_url: str | None = Field(default=None, max_length=1024)
    save: bool = Field(default=True, description="Persist to jc_job")


class EvidenceCitation(BaseModel):
    field_path: str = Field(max_length=256)
    quote: str = Field(min_length=1, max_length=8000)
    entity_id: str | None = None


class RequirementEvidence(BaseModel):
    requirement: str = Field(min_length=1, max_length=4000)
    importance: Literal["required", "preferred", "unspecified"] = "unspecified"
    importance_basis: Literal["jd_explicit", "jd_structure", "estimated"] = "estimated"
    status: Literal["supported", "partial", "unverified"] = "unverified"
    evidence: list[EvidenceCitation] = Field(default_factory=list, max_length=20)
    citation_status: Literal["verified", "unverified"] = "unverified"
    next_question: str | None = Field(default=None, max_length=2000)


class JobResponse(BaseModel):
    id: str
    profile_id: str
    company: str
    title: str
    source_url: str | None
    requirements: dict
    fit_score: int | None
    fit_recommendation: str | None
    fit_gaps: list
    fit_blockers: list
    provenance: dict | None = None
    parsed: JDParseResult | None = None
    evidence_profile_version: int | None = None
    requirement_evidence: list[RequirementEvidence] = Field(default_factory=list)
    fit_summary: str | None = None
    elevate_hints: list[str] = Field(default_factory=list)
    fit_dimensions: dict[str, int] = Field(default_factory=dict)
    legitimacy: str | None = None


class FitScoreRequest(BaseModel):
    job_id: str | None = None
    raw_jd: str | None = Field(default=None, description="Inline JD if job_id omitted")


class FitScoreResponse(BaseModel):
    evidence_profile_version: int | None = None
    requirement_evidence: list[RequirementEvidence] = Field(default_factory=list, max_length=200)
    job_id: str | None
    score: int
    recommendation: Literal["go", "caution", "no"]
    gaps: list[str]
    blockers: list[str]
    summary: str | None = None
    elevate_hints: list[str] = Field(
        default_factory=list, description="按该岗可拔高的方向，不编造经历"
    )
    dimensions: dict[str, int] = Field(
        default_factory=dict,
        description="分维 0–100：match / target / comp / culture / red_flags",
    )
    legitimacy: str | None = Field(
        default=None,
        description="岗位真实性：high | caution | suspicious，不计入 score",
    )


class ParseFromUrlRequest(BaseModel):
    render: bool = Field(default=False, description="Isolated read-only dynamic public page")
    url: str = Field(min_length=8, max_length=1024)
    save: bool = Field(default=True)


class ApplyPipelineRequest(BaseModel):
    job_id: str | None = None
    raw_text: str | None = Field(default=None, description="无 job_id 时粘贴 JD")
    source_url: str | None = None
    elevation_level: str = Field(default="elevated")
    export_format: Literal["pdf", "docx"] = Field(default="pdf")
    create_application: StrictBool = Field(
        default=False, description="仅用户明确确认已实际投递时设为 true；材料导出不等于投递"
    )


class ApplyPipelineResponse(BaseModel):
    job_id: str
    fit: FitScoreResponse
    draft: dict
    export: dict | None = None
    application_id: str | None = None


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    profile_id: str
    resume_variant_id: str | None
    applied_at: str | None
    follow_up_on: str | None = None
    status: str = "evaluated"
    note: str | None
    company: str | None = None
    title: str | None = None
    fit_score: int | None = None
    fit_recommendation: str | None = None


class ApplicationPatchRequest(BaseModel):
    status: Literal[
        "evaluated", "skipped", "applied", "interviewing", "rejected", "offer"
    ] | None = None
    note: str | None = Field(default=None, max_length=1024)
    follow_up_on: str | None = Field(
        default=None, description="跟进日 YYYY-MM-DD；空字符串清除"
    )


class CampaignStatsResponse(BaseModel):
    profile_id: str
    phase: str
    warmup_job_ids: list[str]
    target_job_ids: list[str]
    progress: dict
    fit_calibration: dict
