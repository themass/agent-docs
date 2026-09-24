"""Resolve Content Studio profile root from any skill script location."""

from __future__ import annotations

import os
from pathlib import Path


def find_profile_dir(*, start: Path | None = None) -> Path:
    """Return the Hermes profile directory for Content Studio.

    Resolution order:
    1. ``CONTENT_STUDIO_PROFILE_DIR`` env var
    2. ``HERMES_HOME`` env var
    3. Walk upward from ``start`` looking for ``SOUL.md`` + ``reports/``

    Args:
        start: File or directory to begin upward search from.

    Returns:
        Resolved profile directory path.

    Raises:
        RuntimeError: If no profile directory can be resolved.
    """
    for key in ("CONTENT_STUDIO_PROFILE_DIR", "HERMES_HOME"):
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw).expanduser().resolve()

    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        if (parent / "SOUL.md").is_file() and (parent / "reports").is_dir():
            return parent

    msg = "cannot resolve Content Studio profile directory"
    raise RuntimeError(msg)


def skill_dir(name: str, *, profile_dir: Path | None = None) -> Path:
    """Path to ``skills/content-studio/<name>``."""
    root = profile_dir or find_profile_dir()
    return root / "skills" / "content-studio" / name


def skill_script(skill_name: str, script_name: str, *, profile_dir: Path | None = None) -> Path:
    """Path to a script under ``skills/content-studio/<skill>/scripts/``."""
    return skill_dir(skill_name, profile_dir=profile_dir) / "scripts" / script_name
