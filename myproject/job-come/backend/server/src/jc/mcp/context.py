"""MCP run context — user/profile scope for tool handlers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class McpRunContext:
    db: AsyncSession
    user_id: str | None
    profile_id: str | None
    session_id: str | None = None
    job_id: str | None = None
    mock_session_id: str | None = None


async def require_owned_profile(ctx: McpRunContext, profile_id: str | None = None):
    """Fail closed: an authenticated run may only access its bound, owned profile."""
    from jc.stores.profile_store import ProfileStore

    if not ctx.user_id or not ctx.profile_id:
        raise PermissionError("Authenticated user and bound profile required")
    pid = profile_id or ctx.profile_id
    if pid != ctx.profile_id:
        raise PermissionError("Profile outside this run")
    profile = await ProfileStore(ctx.db).get_by_id(pid)
    if profile is None or profile.user_id != ctx.user_id:
        raise PermissionError("Profile not found or not owned")
    return profile


async def require_owned_references(ctx: McpRunContext, *, job_id=None, mock_session_id=None):
    """Validate relation ownership before creating or mutating records."""
    from jc.stores.interview_store import InterviewStore
    from jc.stores.job_store import JobStore

    if job_id:
        job = await JobStore(ctx.db).get_by_id(job_id)
        if job is None or job.profile_id != ctx.profile_id:
            raise PermissionError("Job outside this profile")
    if mock_session_id:
        mock = await InterviewStore(ctx.db).get_mock_session(mock_session_id)
        if mock is None or mock.profile_id != ctx.profile_id:
            raise PermissionError("Mock session outside this profile")
        from jc.exceptions import ConflictError
        from jc.models.enums import MockSessionStatus
        if mock.status != MockSessionStatus.ACTIVE:
            raise ConflictError("Mock session is no longer active")
        if job_id and mock.job_id and mock.job_id != job_id:
            raise PermissionError("Mock session belongs to another job")
