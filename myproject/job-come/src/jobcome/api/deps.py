"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from agentkit.common.trace import bind_trace_context
from agentkit.web.auth import Actor, GuestActor, UserActor
from jobcome.api.cookies import GUEST_COOKIE, SESSION_COOKIE
from jobcome.capabilities import GUEST_CAPABILITIES, USER_CAPABILITIES
from jobcome.db.session import get_db_session
from jobcome.config import settings
from jobcome.exceptions import AuthError, ForbiddenError
from jobcome.services.agent_service import AgentService
from jobcome.services.session_audit_service import SessionAuditService
from jobcome.services.auth_service import AuthService
from jobcome.services.interview_service import InterviewService
from jobcome.services.application_service import ApplicationService
from jobcome.services.apply_pipeline_service import ApplyPipelineService
from jobcome.services.campaign_service import CampaignService
from jobcome.services.job_service import JobService
from jobcome.services.profile_service import ProfileService
from jobcome.services.resume_service import ResumeService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_profile_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(db)


async def get_resume_service(db: AsyncSession = Depends(get_db)) -> ResumeService:
    return ResumeService(db)


async def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)


async def get_session_audit_service(db: AsyncSession = Depends(get_db)) -> SessionAuditService:
    return SessionAuditService(db)


async def get_coach_service(db: AsyncSession = Depends(get_db)) -> InterviewService:
    return InterviewService(db)


async def get_job_service(db: AsyncSession = Depends(get_db)) -> JobService:
    return JobService(db)


async def get_apply_pipeline_service(db: AsyncSession = Depends(get_db)) -> ApplyPipelineService:
    return ApplyPipelineService(db)


async def get_campaign_service(db: AsyncSession = Depends(get_db)) -> CampaignService:
    return CampaignService(db)


async def get_application_service(db: AsyncSession = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)


def _capabilities_for(actor: Actor) -> tuple[str, ...]:
    if isinstance(actor, UserActor):
        return USER_CAPABILITIES
    return GUEST_CAPABILITIES


def require_capability(capability: str) -> Callable[..., Actor]:
    async def _dep(actor: Actor = Depends(get_actor)) -> Actor:
        if capability not in _capabilities_for(actor):
            raise ForbiddenError(f"Missing capability: {capability}", code="forbidden")
        return actor

    return _dep


async def get_actor(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> Actor:
    session_id = request.cookies.get(SESSION_COOKIE)
    guest_id = request.cookies.get(GUEST_COOKIE)
    try:
        actor = await auth.resolve_actor(session_id=session_id, guest_session_id=guest_id)
    except AuthError:
        actor = GuestActor(guest_session_id=guest_id or "gst_anonymous")
    bind_trace_context(actor_id=actor.actor_id)
    return actor


async def require_user(actor: Actor = Depends(get_actor)) -> UserActor:
    if not isinstance(actor, UserActor):
        raise AuthError("Login required", code="login_required")
    return actor


async def require_admin(request: Request) -> None:
    enabled = settings.job_come_admin_enabled or settings.job_come_env == "development"
    if not enabled:
        raise ForbiddenError("Admin API disabled", code="admin_disabled")
    token = settings.job_come_admin_token.strip()
    if token:
        header = request.headers.get("X-Admin-Token", "")
        if header != token:
            raise AuthError("Invalid admin token", code="admin_token_invalid")
