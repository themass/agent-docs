"""Membership status and redeem-code entry for the signed-in user."""

from __future__ import annotations

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jc.api.deps import get_db, require_user
from jc.schemas.membership import MembershipResponse, RedeemRequest
from jc.services.membership_service import (
    MONTHLY_DAYS,
    MONTHLY_PRICE_CNY,
    MembershipService,
    MembershipSnapshot,
    read_purchase_url,
)

router = APIRouter(prefix="/membership", tags=["membership"])


async def _respond(db: AsyncSession, snapshot: MembershipSnapshot) -> MembershipResponse:
    return MembershipResponse(
        tier=snapshot.tier,
        vip_expires_at=snapshot.vip_expires_at,
        unlimited_download=snapshot.unlimited_download,
        free_download_available=snapshot.free_download_available,
        free_download_used_at=snapshot.free_download_used_at,
        monthly_price_cny=MONTHLY_PRICE_CNY,
        monthly_days=MONTHLY_DAYS,
        purchase_url=await read_purchase_url(db),
    )


@router.get(
    "/me",
    response_model=MembershipResponse,
    summary="当前账号的会员状态与下载次数",
)
async def get_membership(
    actor: UserActor = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> MembershipResponse:
    snapshot = await MembershipService(db).snapshot(actor.user_id)
    return await _respond(db, snapshot)


@router.post(
    "/redeem",
    response_model=MembershipResponse,
    summary="兑换会员码",
    description="每个兑换码只能兑换一次。会员未到期时，新时长接在到期日之后。",
)
async def redeem_code(
    body: RedeemRequest,
    actor: UserActor = Depends(require_user),
    db: AsyncSession = Depends(get_db),
) -> MembershipResponse:
    snapshot = await MembershipService(db).redeem(actor.user_id, body.code)
    return await _respond(db, snapshot)
