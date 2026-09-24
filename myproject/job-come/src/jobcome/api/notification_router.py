"""In-app notification routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agentkit.web.auth import UserActor
from jobcome.api.deps import get_db, require_user
from jobcome.schemas.notification import (
    NotificationDismissRequest,
    NotificationListResponse,
    NotificationReadRequest,
)
from jobcome.services.notification_service import NotificationService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


@router.get("", response_model=NotificationListResponse, summary="消息列表")
async def list_notifications(
    actor: UserActor = Depends(require_user),
    svc: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    return await svc.list_for_actor(actor=actor)


@router.post("/read", response_model=NotificationListResponse, summary="标记已读")
async def mark_notifications_read(
    body: NotificationReadRequest,
    actor: UserActor = Depends(require_user),
    svc: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    return await svc.mark_read(actor=actor, body=body)


@router.post("/dismiss", response_model=NotificationListResponse, summary="关闭消息")
async def dismiss_notifications(
    body: NotificationDismissRequest,
    actor: UserActor = Depends(require_user),
    svc: NotificationService = Depends(get_notification_service),
) -> NotificationListResponse:
    return await svc.dismiss(actor=actor, body=body)
