"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable

from agentkit.common.trace import bind_trace_context
from agentkit.web.auth import Actor, GuestActor, UserActor
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jc.api.cookies import GUEST_COOKIE, SESSION_COOKIE
from jc.capabilities import GUEST_CAPABILITIES, USER_CAPABILITIES
from jc.config import settings
from jc.db.session import get_db_session
from jc.exceptions import AuthError, ForbiddenError
from jc.services.agent_service import AgentService
from jc.services.application_service import ApplicationService
from jc.services.apply_pipeline_service import ApplyPipelineService
from jc.services.auth_service import AuthService
from jc.services.campaign_service import CampaignService
from jc.services.evidence_service import EvidenceService
from jc.services.interview_service import InterviewService
from jc.services.job_service import JobService
from jc.services.profile_service import ProfileService
from jc.services.resume_service import ResumeService
from jc.services.session_audit_service import SessionAuditService
from jc.services.writing_options_service import WritingOptionsService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


async def get_profile_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(db)


async def get_resume_service(db: AsyncSession = Depends(get_db)) -> ResumeService:
    return ResumeService(db)


async def get_evidence_service(db: AsyncSession = Depends(get_db)) -> EvidenceService:
    return EvidenceService(db)


async def get_writing_options_service(
    db: AsyncSession = Depends(get_db),
) -> WritingOptionsService:
    return WritingOptionsService(db)


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
    enabled = settings.jc_admin_enabled or settings.jc_env == "development"
    if not enabled:
        raise ForbiddenError("Admin API disabled", code="admin_disabled")
    token = settings.jc_admin_token.strip()
    if token:
        header = request.headers.get("X-Admin-Token", "")
        if header != token:
            raise AuthError("Invalid admin token", code="admin_token_invalid")
