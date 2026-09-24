"""Profile payload schema tests."""

from jobcome.schemas.profile_payload import ProfilePayload


def test_profile_payload_defaults() -> None:
    payload = ProfilePayload()
    dumped = payload.model_dump()
    assert dumped["contact"]["name"] is None
    assert dumped["experiences"] == []
    assert dumped["constraints"]["forbidden_companies"] == []
