"""Post-process parsed ProfilePayload."""

from __future__ import annotations

import re

from jobcome.models.enums import ConfidenceLevel
from jobcome.schemas.profile_payload import ProfilePayload


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ProfileNormalizer:
    def normalize(self, payload: ProfilePayload) -> ProfilePayload:
        if payload.contact.email and not _EMAIL_RE.match(payload.contact.email):
            payload.contact.email = None
        for exp in payload.experiences:
            if not exp.company or exp.company.startswith("待确认"):
                exp.confidence = ConfidenceLevel.NEEDS_REVIEW
        for edu in payload.education:
            if not edu.school or edu.school.startswith("待确认"):
                edu.confidence = ConfidenceLevel.NEEDS_REVIEW
        return payload
