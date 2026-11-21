"""Immutable profile fingerprinting for run receipts.

The fingerprint covers every reviewed artefact that shapes agent behaviour (A-contract §14), so a run
record can later explain which Soul, role prompts, skills, MCP policy, budget and model wiring produced
a proposal. Files hold ``$ENV`` references only, never secret values.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

PROFILE_NAME_TO_AGENT = {"authoring": "poetry-editor-lead"}

# Always part of the fingerprint; a missing one is a deployment error, not something to skip.
REQUIRED = (
    "config/config.yaml",
    "config/extensions_config.json",
    "config/mcp-policy.yaml",
    "config/budgets.yaml",
    "prompts/core-soul.md",
)
# Hashed when present, in stable order.
OPTIONAL_FILES = ("config/roles.yaml", "config/poetry-policy.yaml")
OPTIONAL_GLOBS = ("prompts/roles/*.md", "skills/*/SKILL.md")


class ProfileError(RuntimeError):
    pass


def profile_root() -> Path:
    return Path(os.getenv("POETRY_AGENT_PROFILE_ROOT", Path(__file__).resolve().parents[3] / "deerflow-profile"))


def fingerprint_inputs(profile_name: str, root: Path | None = None) -> list[Path]:
    if profile_name not in PROFILE_NAME_TO_AGENT:
        raise ProfileError(f"unknown approved profile: {profile_name}")
    root = root or profile_root()
    agent = PROFILE_NAME_TO_AGENT[profile_name]
    required = [root / rel for rel in REQUIRED]
    required += [root / "agents" / agent / "config.yaml", root / "agents" / agent / "SOUL.md"]
    missing = [path for path in required if not path.is_file()]
    if missing:
        relative = ", ".join(sorted(str(path.relative_to(root)) for path in missing))
        raise ProfileError(f"profile artifacts missing: {relative}")
    paths = list(required)
    paths += [root / rel for rel in OPTIONAL_FILES if (root / rel).is_file()]
    for pattern in OPTIONAL_GLOBS:
        paths += [path for path in root.glob(pattern) if path.is_file()]
    # de-duplicate and order by relative path so the digest does not depend on filesystem order
    return sorted(set(paths), key=lambda path: path.relative_to(root).as_posix())


def profile_fingerprint(profile_name: str) -> str:
    root = profile_root()
    digest = hashlib.sha256()
    for path in fingerprint_inputs(profile_name, root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
