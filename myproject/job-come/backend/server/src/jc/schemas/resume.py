"""Resume API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from jc.models.enums import ElevationLevel, ExportFormat


class ResumeDraftResponse(BaseModel):
    id: str
    profile_id: str
    profile_version: int
    elevation_level: str
    locale: str
    template_id: str
    sections: dict[str, Any]
    elevation_map: list[dict[str, Any]]
    reviewer_status: str
    created_at: datetime


class ElevatePreviewResponse(BaseModel):
    draft: ResumeDraftResponse
    html: str
    #: Deterministic check that the draft kept what the profile contains. Returned here
    #: as well as at export because step 3 is where the user can actually act on it —
    #: discovering a dropped accomplishment on the download screen is too late.
    coverage: dict[str, Any] | None = None
    #: Screening measurements (length, bullet count, keyword coverage). Advisory only;
    #: step 3 surfaces the length half, where the user can still change the outcome.
    diagnostics: dict[str, Any] | None = None
    #: What the document-level composition pass did (section order, bullet promotions,
    #: scope-line coverage) and the structural defects it could not fix itself. This is
    #: the answer to "what changed beyond the wording" — without it the user reads a
    #: reordered, re-framed document as nothing but per-sentence polish.
    structure: dict[str, Any] | None = None
    #: The role family's document blueprint and a per-requirement pass/fail for this
    #: draft. This is how "不同岗位有不同的方法论" becomes visible: the user reads the bar
    #: their resume is being judged against, and which parts of it are not yet met.
    blueprint: dict[str, Any] | None = None


class ExportRequest(BaseModel):
    format: ExportFormat = Field(
        default=ExportFormat.PDF, description="导出格式：pdf | docx | html"
    )
    locale: str = Field(default="zh-CN", description="投递语言轨：zh-CN | en-US | zh-en")
    template_id: str | None = Field(default=None, description="HTML 模板 ID；空则按 locale 选择")
    elevation_level: ElevationLevel = Field(
        default=ElevationLevel.ELEVATED,
        description="使用的拔高档位",
    )
    draft_id: str | None = Field(
        default=None,
        description="指定已有 draft；为空则使用最新或自动生成",
    )


class ExportJobResponse(BaseModel):
    id: str
    status: str
    format: str
    download_url: str | None = None
    error_message: str | None = None


class LocalizeRequest(BaseModel):
    source_locale: str | None = Field(default=None, description="原文语言 zh-CN | en-US")
