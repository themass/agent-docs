"""Key-style normalisation for Java responses.

Existing Java records may serialise as camelCase (``auditRefs``) while newer endpoints and the MCP
bridge speak snake_case. Nothing in the repository proves which one the deployed host uses, so every
consumer converts at the boundary instead of guessing.

Dictionaries whose *keys are data* (ids, status names, layer names) must never be rewritten, so a
small set of container fields is passed through untouched.
"""
from __future__ import annotations

import re
from typing import Any

_CAMEL = re.compile(r"(?<=[a-z0-9])([A-Z])")
# Keys that are plain lowercase/underscore words are left alone; only lowerCamel keys are rewritten.
_LOWER_CAMEL = re.compile(r"^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$")
# Container fields whose own keys are identifiers or vocabulary words, not field names.
_OPAQUE_KEYS = frozenset({
    "claim_status_by_id", "content_status_by_id", "version_status_by_id",
    "source_verification_by_id", "claims_by_status", "sources_by_verification",
    "layers", "totals", "payload", "profile_manifest",
})


def to_snake(key: str) -> str:
    return _CAMEL.sub(lambda m: "_" + m.group(1).lower(), key) if _LOWER_CAMEL.match(key) else key


def normalize_keys(value: Any, *, _opaque: bool = False) -> Any:
    """Recursively convert lowerCamel dictionary keys to snake_case."""
    if isinstance(value, list):
        return [normalize_keys(item) for item in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        new_key = key if _opaque else (to_snake(key) if isinstance(key, str) else key)
        out[new_key] = normalize_keys(item, _opaque=isinstance(new_key, str) and new_key in _OPAQUE_KEYS)
    return out
