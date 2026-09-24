"""Profile ownership checks."""

import pytest

from agentkit.web.auth import GuestActor, UserActor
from jobcome.exceptions import ForbiddenError
from jobcome.models.profile import Profile
from jobcome.services.profile_service import ProfileService


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
