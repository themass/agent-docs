"""Ingest parse outcome metadata."""

from __future__ import annotations

from dataclasses import dataclass

from jobcome.schemas.profile_payload import ProfilePayload


@dataclass(frozen=True, slots=True)
class IngestResult:
    payload: ProfilePayload
    mode: str
    warning: str | None = None

    @property
    def is_degraded(self) -> bool:
        return self.mode in {"mock_fallback", "mock_no_text"}
