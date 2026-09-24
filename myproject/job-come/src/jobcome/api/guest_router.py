"""Guest session routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from jobcome.api.cookies import set_guest_cookie
from jobcome.api.deps import get_auth_service
from jobcome.schemas.auth import GuestSessionResponse
from jobcome.services.auth_service import AuthService

router = APIRouter(prefix="/guest", tags=["guest"])


@router.post(
    "/session",
    response_model=GuestSessionResponse,
    summary="创建访客会话",
    description="显式创建访客会话并下发 `jc_guest` Cookie。通常无需单独调用。",
)
async def create_guest_session(
    response: Response,
    auth: AuthService = Depends(get_auth_service),
) -> GuestSessionResponse:
    guest_id = await auth.open_guest_session()
    set_guest_cookie(response, guest_id)
    return GuestSessionResponse(guest_session_id=guest_id)
