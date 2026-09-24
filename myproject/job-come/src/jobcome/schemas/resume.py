"""Resume API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from jobcome.models.enums import ElevationLevel, ExportFormat


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


class ExportRequest(BaseModel):
    format: ExportFormat = Field(default=ExportFormat.PDF, description="导出格式：pdf | docx")
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
