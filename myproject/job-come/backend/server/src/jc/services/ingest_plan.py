"""Pure ingest routing policy: document evidence selects a strategy, not model failures.

No model, storage, database or UI dependencies. A plan is selected once; the
transport owns model failover, while the application owns the overall deadline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IngestRoute(StrEnum):
    TEXT = "text"
    PDF_VISION = "pdf_vision"
    IMAGE_VISION = "image_vision"
    DOCX_VISION = "docx_vision"


@dataclass(frozen=True)
class IngestPlan:
    route: IngestRoute
    reason: str


def usable_text(text: str) -> bool:
    """Conservative signal for extractability, never a judgement of career quality."""
    meaningful = sum(c.isalnum() for c in text)
    return meaningful >= 40 and text.count("\ufffd") / max(1, len(text)) < 0.02


def select_ingest_plan(kind: str, text: str, *, scanned_pages: bool = False) -> IngestPlan:
    if kind == "image":
        return IngestPlan(IngestRoute.IMAGE_VISION, "image_upload")
    if kind == "pdf" and scanned_pages:
        return IngestPlan(IngestRoute.PDF_VISION, "scanned_or_mixed_pages")
    if usable_text(text):
        return IngestPlan(IngestRoute.TEXT, "readable_text_layer")
    if kind == "pdf":
        return IngestPlan(IngestRoute.PDF_VISION, "no_readable_text")
    if kind == "docx":
        return IngestPlan(IngestRoute.DOCX_VISION, "no_readable_text")
    return IngestPlan(IngestRoute.TEXT, "text_only_document")
