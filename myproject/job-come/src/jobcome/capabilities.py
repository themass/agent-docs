"""Capability strings returned by /auth/context."""

from __future__ import annotations

GUEST_CAPABILITIES: tuple[str, ...] = (
    "view",
    "profile_upload",
    "profile_edit",
    "elevate_preview",
)

USER_CAPABILITIES: tuple[str, ...] = GUEST_CAPABILITIES + (
    "export",
    "agent_chat",
    "coach",
    "settings",
)
