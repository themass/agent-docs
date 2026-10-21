"""Canonical JC-owned object-storage key construction."""

from __future__ import annotations

from jc.config import settings

_ENVIRONMENT_ALIASES = {
    "development": "dev",
    "dev": "dev",
    "test": "test",
    "testing": "test",
    "staging": "staging",
    "stage": "staging",
    "production": "prod",
    "prod": "prod",
}


def storage_environment() -> str:
    """Return the canonical object-storage environment segment."""
    configured = settings.jc_env.strip().lower()
    try:
        return _ENVIRONMENT_ALIASES[configured]
    except KeyError as exc:
        supported = ", ".join(sorted(_ENVIRONMENT_ALIASES))
        raise ValueError(
            f"Unsupported JC_ENV {configured!r}; expected one of: {supported}"
        ) from exc


_DOWNLOADABLE_KINDS = frozenset({"export", "photo"})


def profile_id_and_kind_from_key(storage_key: str) -> tuple[str, str] | None:
    """Parse `jc/{env}/profile[s]/{id}/{kind}/...` for authorized local downloads."""
    normalized = storage_key.strip("/")
    if not normalized or ".." in normalized or "\\" in normalized:
        return None
    parts = normalized.split("/")
    try:
        idx = next(i for i, part in enumerate(parts) if part in ("profile", "profiles"))
    except StopIteration:
        return None
    if idx + 2 >= len(parts):
        return None
    profile_id = parts[idx + 1]
    kind = parts[idx + 2]
    if kind not in _DOWNLOADABLE_KINDS:
        return None
    return profile_id, kind


def storage_key(*parts: str) -> str:
    """Build a JC-owned object key without exposing raw user-provided path segments."""
    normalized_parts: list[str] = []
    for part in parts:
        normalized = part.strip("/")
        if not normalized or ".." in normalized or "\\" in normalized:
            raise ValueError("Storage key segments must be non-empty, relative path components")
        normalized_parts.append(normalized)
    if not normalized_parts:
        raise ValueError("Storage key requires at least one path segment")
    return "/".join(("jc", storage_environment(), *normalized_parts))
