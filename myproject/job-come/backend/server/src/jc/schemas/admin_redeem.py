"""Admin schemas for redeem codes and the purchase link."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RedeemCodeItem(BaseModel):
    id: str
    code: str
    batch_id: str
    plan: str
    duration_days: int
    status: str
    expires_at: datetime | None
    note: str | None
    created_at: datetime
    redeemed_at: datetime | None
    redeemed_by_user_id: str | None
    redeemed_by_email: str | None
    voided_at: datetime | None


class RedeemCodeStats(BaseModel):
    total: int
    unused: int
    redeemed: int
    void: int


class RedeemCodeListResponse(BaseModel):
    items: list[RedeemCodeItem]
    total: int
    limit: int
    offset: int
    stats: RedeemCodeStats


class RedeemCodeBatchRequest(BaseModel):
    count: int = Field(ge=1, le=500)
    plan: Literal["monthly"] = "monthly"
    note: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None


class RedeemCodeBatchResponse(BaseModel):
    batch_id: str
    count: int
    codes: list[str]


class RedeemCodeNoteRequest(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class PurchaseUrlRequest(BaseModel):
    url: str | None = Field(default=None, max_length=512)


class PurchaseUrlResponse(BaseModel):
    url: str | None
