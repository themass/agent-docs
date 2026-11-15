"""Contact fields must be refused at the edge, not fail in the database.

Found by an adversarial probe: a ~500-character name returned
`503 database_unavailable` instead of a validation error.

The payload is stored as JSON, so it accepts almost anything — but
`jc_profile.contact_name` is a denormalised `String(128)` column written from
`payload.contact.name`. An over-long name overflowed that column and the driver
error surfaced through the generic handler as "service temporarily unavailable".

Two things were wrong with that, and both are what these tests pin:

1. The user was told to try again later, which is false — retrying the same 500
   characters fails identically.
2. Whoever read the logs was pointed at the database, which was fine; the input
   was the problem.

A 500-character "name" is a mistake or an attack, never a real name.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jc.schemas.profile_payload import ProfileContact, ProfilePayload

#: Every column the payload is denormalised into, and its DB limit.
DENORMALISED = {
    "name": 128,   # jc_profile.contact_name = String(128)
    "email": 254,  # RFC 5321 upper bound
    "phone": 64,
    "location": 128,
}


@pytest.mark.parametrize("field,limit", DENORMALISED.items())
def test_a_field_at_the_limit_is_accepted(field, limit):
    """The boundary itself must still work — an off-by-one here rejects valid data."""
    contact = ProfileContact(**{field: "x" * limit})
    assert getattr(contact, field) == "x" * limit


@pytest.mark.parametrize("field,limit", DENORMALISED.items())
def test_a_field_over_the_limit_is_refused(field, limit):
    with pytest.raises(ValidationError) as exc:
        ProfileContact(**{field: "x" * (limit + 1)})
    # The message must name the field, or the client cannot tell which one to fix.
    assert field in str(exc.value)


def test_the_500_character_name_from_the_report_is_refused():
    """The exact input that produced the 503."""
    long_name = "张" * 500
    with pytest.raises(ValidationError):
        ProfilePayload.model_validate({"contact": {"name": long_name}})


def test_emoji_names_within_the_limit_still_work():
    """Bounding by character count must not break multi-byte names.

    A limit applied to encoded bytes instead of characters would reject a perfectly
    ordinary Chinese name at a third of the stated length.
    """
    contact = ProfileContact(name="张伟😀" * 20)  # 60 characters, 180+ bytes
    assert contact.name is not None
    assert len(contact.name) == 60
