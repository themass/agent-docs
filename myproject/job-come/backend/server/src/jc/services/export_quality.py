"""Fail-closed structural/text checks before exporting any artifact to storage.

These checks do not claim Word pagination or visual typography equivalence.
"""

from __future__ import annotations

import io
import re
from typing import Any


def expected_text(sections: dict[str, Any]) -> list[str]:
    if sections.get("track") == "bilingual":
        return expected_text(sections.get("zh_sections") or {}) + expected_text(
            sections.get("en_sections") or {}
        )
    values = list((sections.get("header") or {}).values()) + [sections.get("summary")]
    for key in ("experience_blocks", "education_blocks", "project_blocks"):
        for block in sections.get(key) or []:
            for field, value in block.items():
                if field in {
                    "company",
                    "title",
                    "date_range",
                    "location",
                    "school",
                    "degree_line",
                    "name",
                    "description",
                    "bullets",
                }:
                    values.extend(value if isinstance(value, list) else [value])
    values.append((sections.get("skills_block") or {}).get("content"))
    return [str(v) for v in values if v]


def _html_to_text(markup: str) -> str:
    """Strip styles and tags so the shared text-retention check can run on HTML."""
    without_style = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", markup)
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_style)
    return (
        without_tags.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )


def validate_export(content: bytes, format: str, sections: dict[str, Any]) -> dict:
    if format == "pdf":
        import fitz

        if not content.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
        with fitz.open(stream=content, filetype="pdf") as document:
            count = document.page_count
            if not 1 <= count <= 6:
                raise ValueError("PDF page count outside 1–6; shorten draft before exporting")
            text = "\n".join(page.get_text() for page in document)
            for page in document:
                for block in page.get_text("blocks"):
                    x0, y0, x1, y1 = block[:4]
                    if x0 < -1 or y0 < -1 or x1 > page.rect.width + 1 or y1 > page.rect.height + 1:
                        raise ValueError("PDF text exceeds page bounds")
    elif format == "docx":
        from docx import Document

        try:
            doc = Document(io.BytesIO(content))
        except Exception as exc:
            raise ValueError("Invalid DOCX package") from exc
        text = "\n".join(p.text for p in doc.paragraphs)
        count = None  # Only Word/LibreOffice can measure actual DOCX pagination.
    elif format == "html":
        try:
            markup = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("HTML export is not valid UTF-8") from exc
        if "<html" not in markup.lower():
            raise ValueError("HTML export missing document root")
        if "<link" in markup.lower() or "<script" in markup.lower():
            # The artifact must render offline and carry no executable payload.
            raise ValueError("HTML export must be self-contained without link/script tags")
        text = _html_to_text(markup)
        count = None  # HTML has no fixed pagination; print CSS governs paper output.
    else:
        raise ValueError("Unsupported export format")

    def normalize(value: str) -> str:
        return re.sub(r"\s+", "", value)

    normalized = normalize(text)
    expected = expected_text(sections)
    missing = [value for value in expected if normalize(value) not in normalized]
    if not expected or missing:
        raise ValueError(f"Export content missing ({len(missing)} fields); revise draft/template")
    return {
        "format": format,
        "pages": count,
        "text_retention": 1.0,
        "checked_fields": len(expected),
    }
