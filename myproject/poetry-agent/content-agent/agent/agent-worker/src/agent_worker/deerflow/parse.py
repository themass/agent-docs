"""Extract ``agent-output/1`` from the last AI message: the last ```json fence wins (contract D5)."""
from __future__ import annotations

import json
import re
from typing import Any

from agent_worker.validate import Violation

_FENCE = re.compile(r"```[ \t]*json[ \t]*\r?\n(.*?)\r?\n```[ \t]*(?=\r?\n|$)", re.IGNORECASE | re.DOTALL)


def extract_output(text: str, max_chars: int) -> tuple[Any, list[Violation]]:
    """Returns ``(parsed_object, [])`` or ``(None, [violations])``. Never quotes the text."""
    if not isinstance(text, str) or not text.strip():
        return None, [Violation("V1", "EMPTY_MESSAGE")]
    if len(text) > max_chars:
        return None, [Violation("V8", "OUTPUT_TOO_LONG", "message")]
    blocks = _FENCE.findall(text)
    if blocks:
        candidate = blocks[-1]
    elif text.strip().startswith("{"):
        candidate = text.strip()
    else:
        return None, [Violation("V1", "NO_JSON_FENCE")]
    try:
        value = json.loads(candidate)
    except ValueError:
        return None, [Violation("V1", "BAD_JSON")]
    if not isinstance(value, dict):
        return None, [Violation("V1", "NOT_OBJECT")]
    return value, []
