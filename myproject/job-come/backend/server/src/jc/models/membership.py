"""Membership ledger, redeem codes, runtime settings, and the admin audit trail."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from jc.db.base import Base
from jc.db.mixins import TimestampMixin
from jc.db.types import JSONText, UTCDateTime


class RedeemCodeStatus(StrEnum):
    UNUSED = "unused"
    REDEEMED = "redeemed"
    VOID = "void"


class RedeemCode(Base, TimestampMixin):
    __tablename__ = "jc_redeem_code"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: Stored normalised (upper case, no separators). Shown with dashes in the UI and CSV.
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    batch_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=RedeemCodeStatus.UNUSED, nullable=False, index=True
    )
    #: When the code itself stops being redeemable. Independent of the membership it grants.
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    redeemed_by_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class MembershipLedger(Base, TimestampMixin):
    """One row per grant of paid time. `redeem_code_id` is unique: a code grants once, ever."""

    __tablename__ = "jc_membership_ledger"
    __table_args__ = (
        UniqueConstraint("redeem_code_id", name="uq_jc_membership_ledger_redeem_code"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    redeem_code_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "jc_app_setting"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class AdminAuditLog(Base, TimestampMixin):
    __tablename__ = "jc_admin_audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    actor_user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONText, nullable=False, default=dict)
