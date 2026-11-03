"""The export header never carries a redaction marker stored as if it were a contact value."""

from __future__ import annotations

import pytest

from jc.schemas.profile_payload import ProfilePayload
from jc.services.resume_draft_builder import ResumeDraftBuilder, _is_redaction_placeholder


def _payload(location: str | None) -> ProfilePayload:
    return ProfilePayload.model_validate({
        "contact": {"name": "李国庆", "location": location, "phone": "15901557296"},
        "experiences": [],
        "summary": "x",
    })


@pytest.mark.parametrize("value", ["[redacted]", "[REDACTED]", "已脱敏", "<redacted>"])
def test_placeholders_are_recognised(value):
    assert _is_redaction_placeholder(value)


@pytest.mark.parametrize("value", ["北京市朝阳区", "redacted-company", "Beijing"])
def test_real_values_are_not_mistaken_for_placeholders(value):
    assert not _is_redaction_placeholder(value)


def test_header_drops_a_placeholder_location_and_keeps_the_phone():
    sections, _ = ResumeDraftBuilder().build(_payload("[redacted]"), elevation_level="conservative")
    assert sections["header"]["contact_line"] == "15901557296"


def test_header_keeps_a_real_location():
    sections, _ = ResumeDraftBuilder().build(
        _payload("北京市朝阳区"), elevation_level="conservative"
    )
    assert sections["header"]["contact_line"] == "北京市朝阳区 · 15901557296"
