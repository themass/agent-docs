"""Deterministic, advisory checks of an extracted PDF text layer.

Inspired by ai-job-search's verify_pdf methodology (see THIRD_PARTY_NOTICES.md).
No model calls, subprocesses, files, or claim of compatibility with every ATS.
Normalization affects comparisons only; never rewrite source facts or artifact bytes.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_PUNCTUATION = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
_DATE_SEPARATOR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)[^\S\n]*[‐‑‒–—―−]")


def normalize_extracted_text(value: str) -> str:
    """Ignore canonical Unicode/typographic differences, not factual differences."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", value).translate(_PUNCTUATION))


def inspect_pdf_text(text: str, sections: dict[str, Any]) -> dict[str, Any]:
    """Only return codes and counts: no resume/contact text enters diagnostic logs."""
    counts = {
        "replacement_character": text.count("\ufffd"),
        "private_use_character": sum(unicodedata.category(c) == "Co" for c in text),
        "non_ascii_date_separator": len(_DATE_SEPARATOR.findall(text)),
    }
    documents = (
        [sections.get("zh_sections") or {}, sections.get("en_sections") or {}]
        if sections.get("track") == "bilingual"
        else [sections]
    )
    contacts = [str((s.get("header") or {}).get("contact_line") or "") for s in documents]
    contacts = [value for value in contacts if value.strip()]
    extracted = normalize_extracted_text(text)
    contact_status = "not_applicable"
    if contacts:
        contact_status = (
            "present"
            if all(normalize_extracted_text(c) in extracted for c in contacts)
            else "missing"
        )
    return {
        "status": "warning" if any(counts.values()) else "checked",
        "checks": {"contact_text": contact_status},
        "warnings": [{"code": code, "count": count} for code, count in counts.items() if count],
        # Sequence alone cannot prove a two-column resume's visual/semantic reading order.
        "reading_order": "not_assessed",
    }
