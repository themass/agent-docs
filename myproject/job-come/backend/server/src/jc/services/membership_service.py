"""Membership tiers, the lifetime free download, and redeem-code redemption.

Concurrency model
-----------------
Two invariants have to hold under concurrent requests, and each is enforced by a single
conditional UPDATE rather than read-check-write:

* A redeem code is granted once: `UPDATE ... WHERE status = 'unused'` must match one row.
* The free download is consumed once: `UPDATE ... WHERE free_download_used_at IS NULL AND
  (no live reservation)` must match one row before rendering starts.

Membership extension reads `vip_expires_at`, so redeem first takes the user row with
`SELECT ... FOR UPDATE` (MySQL; SQLite ignores it, and its single-writer lock is enough).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from agentkit.common.ids import new_id
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from jc.models.enums import UserRole
from jc.models.membership import AppSetting, MembershipLedger, RedeemCode, RedeemCodeStatus
from jc.models.user import User

PLAN_MONTHLY = "monthly"
MONTHLY_DAYS = 30
MONTHLY_PRICE_CNY = 25
PURCHASE_URL_KEY = "purchase_url"

TIER_FREE = "free"
TIER_VIP = "vip"
TIER_ADMIN = "admin"

#: Crockford-style alphabet without 0/O and 1/I/L, so a code read off a screenshot
#: or a CSV is hard to mistype. 16 characters from 32 symbols is 80 bits.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 16

#: A reservation older than this belongs to a render that died; the next export takes it over.
RESERVATION_TTL = timedelta(minutes=15)
REDEEM_MAX_FAILURES = 5
REDEEM_LOCK = timedelta(minutes=15)


def normalize_code(raw: str) -> str:
    """Accept what a buyer actually types: any case, with or without dashes or spaces."""
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def random_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def format_code(code: str) -> str:
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def _now() -> datetime:
    return datetime.now(UTC)


async def read_purchase_url(db: AsyncSession) -> str | None:
    row = await db.get(AppSetting, PURCHASE_URL_KEY)
    return row.value if row is not None and row.value else None


def extend_vip(user: User, days: int, now: datetime) -> tuple[datetime, datetime]:
    """Add paid days. Time stacks on a live membership; a lapsed one is not backfilled."""
    starts_at = (
        user.vip_expires_at
        if user.vip_expires_at is not None and user.vip_expires_at > now
        else now
    )
    ends_at = starts_at + timedelta(days=days)
    user.vip_expires_at = ends_at
    return starts_at, ends_at


def tier_of(user: User, now: datetime) -> str:
    if user.role == UserRole.ADMIN:
        return TIER_ADMIN
    if user.vip_expires_at is not None and user.vip_expires_at > now:
        return TIER_VIP
    return TIER_FREE


@dataclass(frozen=True)
class MembershipSnapshot:
    tier: str
    vip_expires_at: datetime | None
    free_download_used_at: datetime | None

    @property
    def unlimited_download(self) -> bool:
        return self.tier != TIER_FREE

    @property
    def free_download_available(self) -> bool:
        return self.tier == TIER_FREE and self.free_download_used_at is None


class MembershipService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _load_user(self, user_id: str, *, lock: bool = False) -> User:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        if lock:
            stmt = stmt.with_for_update()
        user = (await self._db.execute(stmt)).scalar_one_or_none()
        if user is None:
            raise NotFoundError("账号不存在。", code="user_not_found")
        return user

    async def snapshot(self, user_id: str) -> MembershipSnapshot:
        user = await self._load_user(user_id)
        return MembershipSnapshot(
            tier=tier_of(user, _now()),
            vip_expires_at=user.vip_expires_at,
            free_download_used_at=user.free_download_used_at,
        )

    async def claim_download(self, user_id: str, job_id: str) -> None:
        """Reserve one download before rendering. Members pass straight through."""
        user = await self._load_user(user_id)
        now = _now()
        if tier_of(user, now) != TIER_FREE:
            return
        stale_before = now - RESERVATION_TTL
        result = await self._db.execute(
            update(User)
            .where(
                User.id == user_id,
                User.free_download_used_at.is_(None),
                or_(
                    User.free_download_job_id.is_(None),
                    User.free_download_reserved_at < stale_before,
                ),
            )
            .values(free_download_job_id=job_id, free_download_reserved_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            return
        if user.free_download_used_at is not None:
            raise ForbiddenError(
                "免费下载次数已用完。开通会员后可以不限次数下载。",
                code="download_quota_exhausted",
            )
        raise ForbiddenError(
            "上一份导出还在进行中，请稍候再试。",
            code="download_quota_pending",
        )

    async def consume_download(self, user_id: str, job_id: str) -> None:
        """Mark the free download used. A no-op for members, who never held the claim."""
        await self._db.execute(
            update(User)
            .where(User.id == user_id, User.free_download_job_id == job_id)
            .values(
                free_download_used_at=_now(),
                free_download_job_id=None,
                free_download_reserved_at=None,
            )
            .execution_options(synchronize_session=False)
        )

    async def release_download(self, user_id: str, job_id: str) -> None:
        """Return the reservation after a failed export. A no-op if this job never held it."""
        await self._db.execute(
            update(User)
            .where(
                User.id == user_id,
                User.free_download_job_id == job_id,
                User.free_download_used_at.is_(None),
            )
            .values(free_download_job_id=None, free_download_reserved_at=None)
            .execution_options(synchronize_session=False)
        )

    async def redeem(self, user_id: str, raw_code: str) -> MembershipSnapshot:
        code_value = normalize_code(raw_code)
        user = await self._load_user(user_id, lock=True)
        now = _now()
        if user.redeem_locked_until is not None and user.redeem_locked_until > now:
            raise ForbiddenError("尝试次数过多，请 15 分钟后再试。", code="redeem_locked")

        code = None
        if code_value:
            code = (
                await self._db.execute(select(RedeemCode).where(RedeemCode.code == code_value))
            ).scalar_one_or_none()

        problem = self._redeem_problem(code, now)
        if problem is not None:
            name, message, error_type = problem
            user.redeem_failed_count += 1
            if user.redeem_failed_count >= REDEEM_MAX_FAILURES:
                user.redeem_locked_until = now + REDEEM_LOCK
                user.redeem_failed_count = 0
            await self._db.commit()
            raise error_type(message, code=name)

        assert code is not None
        claimed = await self._db.execute(
            update(RedeemCode)
            .where(RedeemCode.id == code.id, RedeemCode.status == RedeemCodeStatus.UNUSED)
            .values(
                status=RedeemCodeStatus.REDEEMED,
                redeemed_by_user_id=user_id,
                redeemed_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            raise ConflictError("这个兑换码刚刚已被使用。", code="redeem_code_used")

        starts_at, ends_at = extend_vip(user, code.duration_days, now)
        user.redeem_failed_count = 0
        user.redeem_locked_until = None
        self._db.add(
            MembershipLedger(
                id=new_id("mbl"),
                user_id=user_id,
                source="redeem",
                redeem_code_id=code.id,
                days=code.duration_days,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        )
        await self._db.commit()
        return await self.snapshot(user_id)

    @staticmethod
    def _redeem_problem(
        code: RedeemCode | None, now: datetime
    ) -> tuple[str, str, type[AppError]] | None:
        if code is None:
            return ("redeem_code_invalid", "兑换码不正确，请检查后再试。", AppError)
        if code.status == RedeemCodeStatus.VOID:
            return ("redeem_code_void", "这个兑换码已失效。", ConflictError)
        if code.status == RedeemCodeStatus.REDEEMED:
            return ("redeem_code_used", "这个兑换码已被使用。", ConflictError)
        if code.expires_at is not None and code.expires_at <= now:
            return ("redeem_code_expired", "这个兑换码已过期。", ConflictError)
        return None
