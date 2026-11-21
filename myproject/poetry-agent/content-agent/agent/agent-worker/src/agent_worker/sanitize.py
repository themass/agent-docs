"""Untrusted-material handling (contract section 6, rule 7).

Snapshot text, editor instructions and web material are *data*. Before any of it reaches a model it is
stripped of markup, scripts and invisible characters, truncated, and wrapped in an
``<untrusted_material source="...">`` block that the Core Soul tells the model never to obey.
"""
from __future__ import annotations

import html
import re

MAX_BLOCK_CHARS = 6000

# Zero-width, bidi-control and other invisible code points.
_INVISIBLE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff\u00ad\u180e]"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SCRIPT_BLOCK = re.compile(r"<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TAG = re.compile(r"<\s*/?\s*[A-Za-z][^<>]*>?")
_PLACEHOLDER = re.compile(r"^\s*$|^\s*(?:待.*|未核对.*|tbd|todo|n/?a|\?+|-+|…+)\s*$", re.IGNORECASE | re.DOTALL)
_PLACEHOLDER_WORDS = ("待核查", "待人工", "未核对", "待指定", "待核对", "TBD")


def strip_markup(text: str) -> str:
    """Remove HTML/script/comments, entity-decode, drop invisible and control characters."""
    if not isinstance(text, str):
        text = str(text)
    text = _INVISIBLE.sub("", text)
    text = _CONTROL.sub("", text)
    for _ in range(3):  # entity decoding can reveal new tags; iterate to a fixed point
        before = text
        text = _SCRIPT_BLOCK.sub(" ", text)
        text = _COMMENT.sub(" ", text)
        text = _TAG.sub(" ", text)
        text = html.unescape(text)
        text = _INVISIBLE.sub("", text)
        if text == before:
            break
    # Anything angle-bracket-shaped that survives could forge a wrapper tag: neutralise it.
    return text.replace("<", "＜").replace(">", "＞")


def truncate(text: str, limit: int = MAX_BLOCK_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 12)] + "…[已截断]"


def clean(text: str, limit: int = MAX_BLOCK_CHARS) -> str:
    return truncate(strip_markup(text), limit)


def _source_attr(source: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:/#-]", "_", source)[:80] or "unknown"


def wrap_untrusted(text: str, source: str, limit: int = MAX_BLOCK_CHARS) -> str:
    """One bounded ``<untrusted_material>`` block."""
    return f'<untrusted_material source="{_source_attr(source)}">\n{clean(text, limit)}\n</untrusted_material>'


def wrap_untrusted_blocks(text: str, source: str, limit: int = MAX_BLOCK_CHARS) -> list[str]:
    """Split long material into several blocks, each at most ``limit`` characters of content."""
    cleaned = strip_markup(text)
    if not cleaned.strip():
        return [wrap_untrusted("", source, limit)]
    blocks: list[str] = []
    current = ""
    for line in cleaned.split("\n"):
        while len(line) > limit:
            if current:
                blocks.append(current)
                current = ""
            blocks.append(line[:limit])
            line = line[limit:]
        if current and len(current) + len(line) + 1 > limit:
            blocks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        blocks.append(current)
    total = len(blocks)
    return [
        f'<untrusted_material source="{_source_attr(source)}" part="{i}/{total}">\n{b}\n</untrusted_material>'
        for i, b in enumerate(blocks, 1)
    ]


def is_placeholder(value: object) -> bool:
    """True for an empty or stand-in locator (Java ``locator_state`` MISSING/PLACEHOLDER)."""
    if value is None:
        return True
    text = str(value).strip()
    if not text or _PLACEHOLDER.match(text):
        return True
    return text.startswith("待") or any(word in text for word in _PLACEHOLDER_WORDS)
