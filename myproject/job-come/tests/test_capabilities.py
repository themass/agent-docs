"""Auth capability constants."""

from jobcome.capabilities import GUEST_CAPABILITIES, USER_CAPABILITIES


def test_user_capabilities_extend_guest() -> None:
    assert set(GUEST_CAPABILITIES).issubset(USER_CAPABILITIES)
    assert "export" in USER_CAPABILITIES
    assert "export" not in GUEST_CAPABILITIES
