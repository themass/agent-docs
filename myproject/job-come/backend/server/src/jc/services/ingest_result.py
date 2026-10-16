"""Profile-ingest outcome metadata."""

from __future__ import annotations

from dataclasses import dataclass

from jc.schemas.profile_payload import ProfilePayload


@dataclass(frozen=True, slots=True)
class IngestResult:
    payload: ProfilePayload
    mode: str
    warning: str | None = None
    # Which extractor produced the text/images that informed the chosen profile draft.
    # This is deliberately a small audited vocabulary, not an arbitrary provider string.
    extraction_source: str = "native_text"

    @property
    def is_degraded(self) -> bool:
        return self.mode in {"mock_fallback", "mock_no_text"}
