"""Bounded, advisory diagnostics for untrusted JD input. Not an injection firewall.

Preserve the input verbatim. Return counts/codes only, never snippets or URLs.
This pure function cannot fetch links, execute instructions, or change user facts.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")
_INSTRUCTION = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions"
    r"|(?:system|developer)\s*(?:prompt|message)\s*:"
    r"|忽略.{0,12}(?:之前|以上|系统|所有).{0,8}(?:指令|要求|规则)"
    r"|(?:泄露|输出|打印).{0,8}(?:系统提示词|API.?KEY|密钥)",
    re.IGNORECASE,
)
_HIDDEN_STYLE = re.compile(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE)


class _HiddenMarkup(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            "hidden" in attributes
            or (attributes.get("aria-hidden") or "").lower() == "true"
            or _HIDDEN_STYLE.search(attributes.get("style") or "")
        ):
            self.count += 1


def inspect_jd_text(text: str) -> dict[str, Any]:
    # Bound work, and disclose that suffixes were not scanned. Scan is advisory only.
    sample = text[:50_000]
    markup = _HiddenMarkup()
    markup.feed(sample)
    markup.close()
    counts = {
        "hidden_markup": markup.count,
        "invisible_character": len(_INVISIBLE.findall(sample)),
        "instruction_shaped_text": len(_INSTRUCTION.findall(sample)),
    }
    return {
        "version": 1,
        "untrusted_content": True,
        "status": "warning" if any(counts.values()) else "checked",
        "truncated": len(text) > len(sample),
        "warnings": [{"code": code, "count": count} for code, count in counts.items() if count],
    }
