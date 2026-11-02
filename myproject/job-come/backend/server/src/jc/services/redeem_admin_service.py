"""Admin operations on redeem codes, the purchase link, and the admin audit trail."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from agentkit.common.ids import new_id
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.exceptions import AppError, ConflictError, NotFoundError
from jc.models.membership import (
    AdminAuditLog,
    AppSetting,
    MembershipLedger,
    RedeemCode,
    RedeemCodeStatus,
)
from jc.models.user import User
from jc.schemas.admin_redeem import (
    MembershipGiftResponse,
    RedeemCodeBatchResponse,
    RedeemCodeItem,
    RedeemCodeListResponse,
    RedeemCodeStats,
)
from jc.services.membership_service import (
    MONTHLY_DAYS,
    PLAN_MONTHLY,
    PURCHASE_URL_KEY,
    extend_vip,
    format_code,
    normalize_code,
    random_code,
    read_purchase_url,
)

PLAN_GIFT = "gift"
GIFT_MIN_DAYS = 1
GIFT_MAX_DAYS = 365
_MAX_BATCH = 500
_CODE_GENERATION_ATTEMPTS = 10


class RedeemAdminService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_batch(
        self,
        *,
        actor_user_id: str,
        count: int,
        note: str | None,
        expires_at: datetime | None,
    ) -> RedeemCodeBatchResponse:
        if not 1 <= count <= _MAX_BATCH:
            raise AppError(f"一次最多生成 {_MAX_BATCH} 个兑换码。", code="batch_too_large")
        codes = await self._unused_codes(count)
        batch_id = new_id("rdb")
        for code in codes:
            self._db.add(
                RedeemCode(
                    id=new_id("rdc"),
                    code=code,
                    batch_id=batch_id,
                    plan=PLAN_MONTHLY,
                    duration_days=MONTHLY_DAYS,
                    status=RedeemCodeStatus.UNUSED,
                    expires_at=expires_at,
                    note=note,
                    created_by=actor_user_id,
                )
            )
        self._audit(
            actor_user_id,
            "redeem_batch.create",
            "redeem_batch",
            batch_id,
            {"count": count, "plan": PLAN_MONTHLY, "expires_at": _iso(expires_at)},
        )
        await self._db.commit()
        return RedeemCodeBatchResponse(
            batch_id=batch_id,
            count=count,
            codes=[format_code(code) for code in codes],
        )

    async def gift_membership(
        self,
        *,
        actor_user_id: str,
        email: str,
        days: int,
        note: str | None,
    ) -> MembershipGiftResponse:
        """Grant paid days to one account by email, recorded as an already-redeemed code.

        Writing the grant as a redeemed code row keeps one history of who received paid
        time and from which operator, instead of a second list that has to be reconciled
        with the first.
        """
        if not GIFT_MIN_DAYS <= days <= GIFT_MAX_DAYS:
            raise AppError(
                f"赠送天数需要在 {GIFT_MIN_DAYS} 到 {GIFT_MAX_DAYS} 之间。",
                code="invalid_gift_days",
            )
        address = email.strip().lower()
        user = (
            await self._db.execute(
                select(User)
                .where(func.lower(User.email) == address, User.deleted_at.is_(None))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError("没有找到这个邮箱对应的账号。", code="gift_user_not_found")

        now = datetime.now(UTC)
        _, ends_at = extend_vip(user, days, now)
        code_id = new_id("rdc")
        batch_id = new_id("rdb")
        self._db.add(
            RedeemCode(
                id=code_id,
                code=f"GIFT{secrets.token_hex(6).upper()}",
                batch_id=batch_id,
                plan=PLAN_GIFT,
                duration_days=days,
                status=RedeemCodeStatus.REDEEMED,
                note=note or "管理员赠送",
                created_by=actor_user_id,
                redeemed_by_user_id=user.id,
                redeemed_at=now,
            )
        )
        await self._db.flush()
        self._db.add(
            MembershipLedger(
                id=new_id("mbl"),
                user_id=user.id,
                source="gift",
                redeem_code_id=code_id,
                days=days,
                starts_at=ends_at - timedelta(days=days),
                ends_at=ends_at,
            )
        )
        self._audit(
            actor_user_id,
            "membership.gift",
            "user",
            user.id,
            {"email": user.email, "days": days, "code_id": code_id, "note": note},
        )
        await self._db.commit()
        return MembershipGiftResponse(
            user_id=user.id,
            email=user.email,
            days=days,
            vip_expires_at=ends_at,
            code_id=code_id,
        )

    async def _unused_codes(self, count: int) -> list[str]:
        """Random codes that do not collide with any existing row, not just each other."""
        codes: set[str] = set()
        for _ in range(_CODE_GENERATION_ATTEMPTS):
            while len(codes) < count:
                codes.add(random_code())
            taken = set(
                (
                    await self._db.execute(
                        select(RedeemCode.code).where(RedeemCode.code.in_(list(codes)))
                    )
                )
                .scalars()
                .all()
            )
            if not taken:
                return sorted(codes)
            codes -= taken
        raise AppError("兑换码生成冲突，请重试。", code="code_generation_collision")

    async def list_codes(
        self,
        *,
        status: str | None,
        batch_id: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> RedeemCodeListResponse:
        filters = []
        if status:
            filters.append(RedeemCode.status == _validated_status(status))
        if batch_id:
            filters.append(RedeemCode.batch_id == batch_id)
        if search:
            needle = normalize_code(search)
            if needle:
                filters.append(
                    or_(
                        RedeemCode.code.contains(needle),
                        RedeemCode.note.contains(search.strip()),
                    )
                )

        total = (
            await self._db.execute(select(func.count()).select_from(RedeemCode).where(*filters))
        ).scalar_one()
        rows = (
            await self._db.execute(
                select(RedeemCode, User.email)
                .outerjoin(User, User.id == RedeemCode.redeemed_by_user_id)
                .where(*filters)
                .order_by(RedeemCode.created_at.desc(), RedeemCode.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
        stats_rows = (
            await self._db.execute(
                select(RedeemCode.status, func.count()).group_by(RedeemCode.status)
            )
        ).all()
        counts = {str(row[0]): int(row[1]) for row in stats_rows}
        stats = RedeemCodeStats(
            total=sum(counts.values()),
            unused=counts.get(RedeemCodeStatus.UNUSED, 0),
            redeemed=counts.get(RedeemCodeStatus.REDEEMED, 0),
            void=counts.get(RedeemCodeStatus.VOID, 0),
        )
        return RedeemCodeListResponse(
            items=[_item(code, email) for code, email in rows],
            total=total,
            limit=limit,
            offset=offset,
            stats=stats,
        )

    async def get_code(self, code_id: str) -> RedeemCodeItem:
        code, email = await self._load(code_id)
        return _item(code, email)

    async def update_note(
        self, *, actor_user_id: str, code_id: str, note: str | None
    ) -> RedeemCodeItem:
        code, email = await self._load(code_id)
        code.note = note
        self._audit(actor_user_id, "redeem_code.note", "redeem_code", code_id, {"note": note})
        await self._db.commit()
        return _item(code, email)

    async def void_code(self, *, actor_user_id: str, code_id: str) -> RedeemCodeItem:
        code, email = await self._load(code_id)
        if code.status != RedeemCodeStatus.UNUSED:
            raise ConflictError(
                "只能作废未使用的兑换码，已兑换的记录会保留。",
                code="redeem_code_not_voidable",
            )
        code.status = RedeemCodeStatus.VOID
        code.voided_at = datetime.now(UTC)
        self._audit(actor_user_id, "redeem_code.void", "redeem_code", code_id, {})
        await self._db.commit()
        return _item(code, email)

    async def delete_code(self, *, actor_user_id: str, code_id: str) -> None:
        """Hard delete, for codes created by mistake. Anything redeemed is kept for audit."""
        code, _ = await self._load(code_id)
        if code.status != RedeemCodeStatus.UNUSED:
            raise ConflictError(
                "只能删除未使用的兑换码，已兑换或已作废的记录会保留。",
                code="redeem_code_not_deletable",
            )
        await self._db.delete(code)
        self._audit(actor_user_id, "redeem_code.delete", "redeem_code", code_id, {})
        await self._db.commit()

    async def export_csv_rows(
        self, *, actor_user_id: str, status: str | None, batch_id: str | None
    ) -> list[RedeemCodeItem]:
        filters = [RedeemCode.status == _validated_status(status or RedeemCodeStatus.UNUSED)]
        if batch_id:
            filters.append(RedeemCode.batch_id == batch_id)
        rows = (
            await self._db.execute(
                select(RedeemCode, User.email)
                .outerjoin(User, User.id == RedeemCode.redeemed_by_user_id)
                .where(*filters)
                .order_by(RedeemCode.batch_id, RedeemCode.created_at, RedeemCode.id)
            )
        ).all()
        self._audit(
            actor_user_id,
            "redeem_code.export",
            "redeem_batch" if batch_id else "redeem_code",
            batch_id,
            {"status": status or RedeemCodeStatus.UNUSED, "count": len(rows)},
        )
        await self._db.commit()
        return [_item(code, email) for code, email in rows]

    async def get_purchase_url(self) -> str | None:
        return await read_purchase_url(self._db)

    async def set_purchase_url(self, *, actor_user_id: str, url: str | None) -> str | None:
        cleaned = (url or "").strip()
        if cleaned and not cleaned.startswith(("https://", "http://")):
            raise AppError("购买链接需要以 http:// 或 https:// 开头。", code="invalid_purchase_url")
        row = await self._db.get(AppSetting, PURCHASE_URL_KEY)
        if row is None:
            row = AppSetting(key=PURCHASE_URL_KEY, value=cleaned, updated_by=actor_user_id)
            self._db.add(row)
        else:
            row.value = cleaned
            row.updated_by = actor_user_id
        self._audit(
            actor_user_id,
            "app_setting.purchase_url",
            "app_setting",
            PURCHASE_URL_KEY,
            {"url": cleaned or None},
        )
        await self._db.commit()
        return cleaned or None

    async def _load(self, code_id: str) -> tuple[RedeemCode, str | None]:
        row = (
            await self._db.execute(
                select(RedeemCode, User.email)
                .outerjoin(User, User.id == RedeemCode.redeemed_by_user_id)
                .where(RedeemCode.id == code_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("没有这个兑换码。", code="redeem_code_not_found")
        return row[0], row[1]

    def _audit(
        self,
        actor_user_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        detail: dict,
    ) -> None:
        self._db.add(
            AdminAuditLog(
                id=new_id("aud"),
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=detail,
            )
        )


def _validated_status(value: str) -> str:
    try:
        return RedeemCodeStatus(value)
    except ValueError as exc:
        raise AppError("状态只能是 unused、redeemed 或 void。", code="invalid_status") from exc


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _item(code: RedeemCode, email: str | None) -> RedeemCodeItem:
    return RedeemCodeItem(
        id=code.id,
        code=format_code(code.code),
        batch_id=code.batch_id,
        plan=code.plan,
        duration_days=code.duration_days,
        status=code.status,
        expires_at=code.expires_at,
        note=code.note,
        created_at=code.created_at,
        redeemed_at=code.redeemed_at,
        redeemed_by_user_id=code.redeemed_by_user_id,
        redeemed_by_email=email,
        voided_at=code.voided_at,
    )
