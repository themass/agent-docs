"""Resume draft builder tests."""

from jobcome.models.enums import ElevationLevel
from jobcome.schemas.profile_payload import ProfileContact, ProfileExperience, ProfilePayload
from jobcome.services.resume_draft_builder import ResumeDraftBuilder


def test_elevate_changes_bullets() -> None:
    profile = ProfilePayload(
        contact=ProfileContact(name="张三"),
        experiences=[
            ProfileExperience(
                id="exp1",
                company="ACME",
                title="工程师",
                start_date="2020-01",
                highlights=["参与订单系统开发"],
            )
        ],
    )
    sections, elevation_map = ResumeDraftBuilder().build(
        profile,
        elevation_level=ElevationLevel.ELEVATED,
    )
    bullet = sections["experience_blocks"][0]["bullets"][0]
    assert bullet != "参与订单系统开发"
    assert elevation_map
