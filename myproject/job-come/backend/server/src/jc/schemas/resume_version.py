"""Resume versions: every optimised draft a profile has produced, and the files exported from it."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResumeVersionJob(BaseModel):
    id: str
    title: str
    company: str


class ResumeVersionExport(BaseModel):
    id: str
    format: str
    status: str
    completed_at: datetime | None = None
    download_url: str | None = None
    error_message: str | None = None


class ResumeVersionItem(BaseModel):
    id: str
    created_at: datetime
    job: ResumeVersionJob | None = Field(description="None for a generic, not job-targeted, version")
    elevation_level: str
    locale: str
    template_id: str
    reviewer_status: str
    exports: list[ResumeVersionExport]


class ResumeVersionGroup(BaseModel):
    profile_id: str
    contact_name: str | None = None
    is_active: bool
    versions: list[ResumeVersionItem]


class ResumeVersionListResponse(BaseModel):
    groups: list[ResumeVersionGroup]
