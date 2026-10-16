"""Profile ownership checks."""

import pytest
from agentkit.web.auth import GuestActor, UserActor

from jc.exceptions import ForbiddenError
from jc.models.profile import Profile
from jc.services.profile_service import ProfileService


def test_assert_owner_user_match() -> None:
    profile = Profile(id="prof_test", user_id="usr_a", guest_session_id=None)
    actor = UserActor(user_id="usr_a", session_id="sess_x")
    ProfileService._assert_owner(profile, actor)


def test_assert_owner_user_mismatch() -> None:
    profile = Profile(id="prof_test", user_id="usr_a", guest_session_id=None)
    actor = UserActor(user_id="usr_b", session_id="sess_x")
    with pytest.raises(ForbiddenError):
        ProfileService._assert_owner(profile, actor)


def test_assert_owner_guest_match() -> None:
    profile = Profile(id="prof_test", user_id=None, guest_session_id="gst_a")
    actor = GuestActor(guest_session_id="gst_a")
    ProfileService._assert_owner(profile, actor)


@pytest.mark.asyncio
async def test_update_version_conflict_raises_conflict_error() -> None:
    """A stale expected_version must surface as ConflictError, not NameError.

    ConflictError was referenced here without being imported, so this branch raised
    NameError and the endpoint returned 500 instead of a 409 the client can act on.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from jc.exceptions import ConflictError
    from jc.schemas.profile import ProfileUpdateRequest
    from jc.schemas.profile_payload import ProfilePayload

    profile = Profile(id="prof_test", user_id="usr_a", guest_session_id=None, version=7)
    service = object.__new__(ProfileService)
    service._profiles = SimpleNamespace(get_by_id=AsyncMock(return_value=profile))
    service._db = SimpleNamespace(commit=AsyncMock())

    body = ProfileUpdateRequest(payload=ProfilePayload.model_validate({}), expected_version=3)

    with pytest.raises(ConflictError) as excinfo:
        await service.update(
            "prof_test",
            actor=UserActor(user_id="usr_a", session_id="sess_x"),
            body=body,
        )

    assert excinfo.value.code == "version_conflict"
    # A rejected write must not be committed and must not bump the version.
    service._db.commit.assert_not_awaited()
    assert profile.version == 7
