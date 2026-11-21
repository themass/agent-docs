"""Key-style normalisation of Java responses (contract section 14).

Nothing in the repository proves whether the deployed Java host serialises ``taskId`` or ``task_id``,
so every consumer converts at the boundary. Mirrors ``agent_bff.normalize``: dictionaries whose *keys
are data* (ids, vocabulary words) are never rewritten.
"""
from __future__ import annotations

import re
from typing import Any

_CAMEL = re.compile(r"(?<=[a-z0-9])([A-Z])")
_LOWER_CAMEL = re.compile(r"^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$")
OPAQUE_KEYS = frozenset({
    "claim_status_by_id", "content_status_by_id", "version_status_by_id",
    "source_verification_by_id", "claims_by_status", "sources_by_verification",
    "layers", "totals", "payload",
})


def to_snake(key: str) -> str:
    return _CAMEL.sub(lambda m: "_" + m.group(1).lower(), key) if _LOWER_CAMEL.match(key) else key


def normalize_keys(value: Any, *, _opaque: bool = False) -> Any:
    """Recursively convert lowerCamel dictionary keys to snake_case (opaque containers untouched)."""
    if isinstance(value, list):
        return [normalize_keys(item) for item in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        new_key = key if _opaque or not isinstance(key, str) else to_snake(key)
        out[new_key] = normalize_keys(item, _opaque=isinstance(new_key, str) and new_key in OPAQUE_KEYS)
    return out
