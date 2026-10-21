"""Ownership guards — fail closed before any scoped read or write.

Every one of these raises rather than returning a boolean. A caller that forgets to
check a boolean silently leaks data belonging to someone else; a caller that forgets to await a
guard fails loudly in tests. That asymmetry is the whole reason for the shape.
"""

from __future__ import annotations

from jc.authz.scope import RunScope


async def require_owned_profile(scope: RunScope, profile_id: str | None = None):
    """Fail closed: a run may only access the bound profile, and only if it owns it."""
    from jc.stores.profile_store import ProfileStore

    if not scope.user_id or not scope.profile_id:
        raise PermissionError("Authenticated user and bound profile required")
    pid = profile_id or scope.profile_id
    if pid != scope.profile_id:
        raise PermissionError("Profile outside this run")
    profile = await ProfileStore(scope.db).get_by_id(pid)
    if profile is None or profile.user_id != scope.user_id:
        raise PermissionError("Profile not found or not owned")
    return profile


async def require_owned_references(scope: RunScope, *, job_id=None, mock_session_id=None):
    """Validate relation ownership before creating or mutating records."""
    from jc.stores.interview_store import InterviewStore
    from jc.stores.job_store import JobStore

    if job_id:
        job = await JobStore(scope.db).get_by_id(job_id)
        if job is None or job.profile_id != scope.profile_id:
            raise PermissionError("Job outside this profile")
    if mock_session_id:
        mock = await InterviewStore(scope.db).get_mock_session(mock_session_id)
        if mock is None or mock.profile_id != scope.profile_id:
            raise PermissionError("Mock session outside this profile")
        from jc.exceptions import ConflictError
        from jc.models.enums import MockSessionStatus
        if mock.status != MockSessionStatus.ACTIVE:
            raise ConflictError("这场模拟面试已经结束了。", code="mock_session_closed")
        if job_id and mock.job_id and mock.job_id != job_id:
            raise PermissionError("Mock session belongs to another job")
