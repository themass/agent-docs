"""Membership API schemas for the signed-in user."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MembershipResponse(BaseModel):
    tier: Literal["free", "vip", "admin"]
    vip_expires_at: datetime | None
    unlimited_download: bool
    free_download_available: bool
    free_download_used_at: datetime | None
    monthly_price_cny: int
    monthly_days: int
    purchase_url: str | None


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=64)
