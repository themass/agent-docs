"""Admin routes for redeem codes and the purchase link."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Annotated

from agentkit.web.auth import UserActor
from fastapi import APIRouter, Depends, Query, Response

from jc.api.deps import get_redeem_admin_service, require_admin
from jc.schemas.admin_redeem import (
    MembershipGiftRequest,
    MembershipGiftResponse,
    PurchaseUrlRequest,
    PurchaseUrlResponse,
    RedeemCodeBatchRequest,
    RedeemCodeBatchResponse,
    RedeemCodeItem,
    RedeemCodeListResponse,
    RedeemCodeNoteRequest,
)
from jc.services.redeem_admin_service import RedeemAdminService

router = APIRouter(prefix="/admin", tags=["admin"])

_Limit = Annotated[int, Query(ge=1, le=200)]
_Offset = Annotated[int, Query(ge=0)]
_Status = Annotated[
    str | None,
    Query(pattern="^(unused|redeemed|void)$", description="unused / redeemed / void"),
]

#: Spreadsheet apps evaluate a cell that begins with one of these characters as a formula.
#: Notes are free text typed by an operator, so they are neutralised before export.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_CSV_HEADER = [
    "兑换码",
    "批次",
    "档位",
    "时长（天）",
    "状态",
    "备注",
    "生成时间",
    "兑换账号",
    "兑换时间",
]


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


@router.get(
    "/redeem-codes",
    response_model=RedeemCodeListResponse,
    summary="兑换码列表（含各状态统计）",
)
async def admin_list_redeem_codes(
    limit: _Limit = 50,
    offset: _Offset = 0,
    status: _Status = None,
    batch_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(description="按兑换码或备注模糊匹配")] = None,
    _: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> RedeemCodeListResponse:
    return await service.list_codes(
        status=status,
        batch_id=batch_id,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/redeem-codes/batches",
    response_model=RedeemCodeBatchResponse,
    summary="批量生成兑换码",
    description="生成后即可在列表和 CSV 中看到完整码。码本身不写入审计日志。",
)
async def admin_create_redeem_batch(
    body: RedeemCodeBatchRequest,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> RedeemCodeBatchResponse:
    return await service.create_batch(
        actor_user_id=actor.user_id,
        count=body.count,
        note=body.note,
        expires_at=body.expires_at,
    )


@router.get(
    "/redeem-codes/export.csv",
    summary="导出兑换码 CSV（用于咸鱼上架对照）",
    description="默认只导出未使用的码。必须在 `/redeem-codes/{code_id}` 之前声明。",
)
async def admin_export_redeem_codes(
    status: _Status = None,
    batch_id: Annotated[str | None, Query()] = None,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> Response:
    items = await service.export_csv_rows(
        actor_user_id=actor.user_id,
        status=status,
        batch_id=batch_id,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADER)
    for item in items:
        writer.writerow(
            [
                _csv_cell(item.code),
                _csv_cell(item.batch_id),
                _csv_cell(item.plan),
                _csv_cell(item.duration_days),
                _csv_cell(item.status),
                _csv_cell(item.note),
                _csv_cell(item.created_at.isoformat() if item.created_at else ""),
                _csv_cell(item.redeemed_by_email),
                _csv_cell(item.redeemed_at.isoformat() if item.redeemed_at else ""),
            ]
        )
    # UTF-8 BOM so Excel on Windows does not read the Chinese headers as mojibake.
    body = ("\ufeff" + buffer.getvalue()).encode("utf-8")
    filename = f"redeem-codes-{datetime.now(UTC):%Y%m%d-%H%M%S}.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/redeem-codes/{code_id}",
    response_model=RedeemCodeItem,
    summary="兑换码详情",
)
async def admin_get_redeem_code(
    code_id: str,
    _: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> RedeemCodeItem:
    return await service.get_code(code_id)


@router.patch(
    "/redeem-codes/{code_id}",
    response_model=RedeemCodeItem,
    summary="修改兑换码备注（任何状态都可改）",
)
async def admin_update_redeem_note(
    code_id: str,
    body: RedeemCodeNoteRequest,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> RedeemCodeItem:
    return await service.update_note(actor_user_id=actor.user_id, code_id=code_id, note=body.note)


@router.post(
    "/redeem-codes/{code_id}/void",
    response_model=RedeemCodeItem,
    summary="作废未使用的兑换码",
)
async def admin_void_redeem_code(
    code_id: str,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> RedeemCodeItem:
    return await service.void_code(actor_user_id=actor.user_id, code_id=code_id)


@router.delete(
    "/redeem-codes/{code_id}",
    status_code=204,
    summary="删除未使用的兑换码（生成错误时用）",
)
async def admin_delete_redeem_code(
    code_id: str,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> Response:
    await service.delete_code(actor_user_id=actor.user_id, code_id=code_id)
    return Response(status_code=204)


@router.post(
    "/membership/gift",
    response_model=MembershipGiftResponse,
    summary="按邮箱赠送会员",
    description="立即生效，时长接在对方当前到期日之后。会写入一条已兑换的记录和审计日志。",
)
async def admin_gift_membership(
    body: MembershipGiftRequest,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> MembershipGiftResponse:
    return await service.gift_membership(
        actor_user_id=actor.user_id,
        email=body.email,
        days=body.days,
        note=body.note,
    )


@router.get(
    "/membership/purchase-url",
    response_model=PurchaseUrlResponse,
    summary="读取购买入口链接",
)
async def admin_get_purchase_url(
    _: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> PurchaseUrlResponse:
    return PurchaseUrlResponse(url=await service.get_purchase_url())


@router.put(
    "/membership/purchase-url",
    response_model=PurchaseUrlResponse,
    summary="设置购买入口链接（咸鱼商品页）",
)
async def admin_set_purchase_url(
    body: PurchaseUrlRequest,
    actor: UserActor = Depends(require_admin),
    service: RedeemAdminService = Depends(get_redeem_admin_service),
) -> PurchaseUrlResponse:
    url = await service.set_purchase_url(actor_user_id=actor.user_id, url=body.url)
    return PurchaseUrlResponse(url=url)
