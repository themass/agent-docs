"""MCP run context — user/profile scope for tool handlers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class McpRunContext:
    db: AsyncSession
    user_id: str | None
    profile_id: str | None
    session_id: str | None = None
    job_id: str | None = None
