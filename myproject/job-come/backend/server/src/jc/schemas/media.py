"""Direct-upload API schemas (ADR-011)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaSignRequest(BaseModel):
    scene: str = Field(description="上传场景：chat-image / chat-audio / profile-source")
    content_type: str = Field(alias="contentType", max_length=128)
    size_bytes: int = Field(alias="sizeBytes", ge=1)


class MediaUploadInstruction(BaseModel):
    method: str = "PUT"
    url: str = Field(description="预签名 PUT URL —— bearer secret，禁止写日志/埋点")
    headers: dict[str, str] = Field(
        description="必须原样携带的请求头；Content-Type 已算进签名，改动会 403"
    )
    expires_at: datetime


class MediaLimits(BaseModel):
    model_config = {"populate_by_name": True}

    max_bytes: int = Field(alias="maxBytes")


class MediaSignResponse(BaseModel):
    model_config = {"populate_by_name": True}

    object_key: str = Field(alias="objectKey")
    upload: MediaUploadInstruction
    limits: MediaLimits
