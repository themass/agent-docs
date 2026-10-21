"""Run scope — the identity and database handle a single piece of work runs under.

This is deliberately *not* an MCP type. Agent tool calls, HTTP handlers and offline
scripts all need the same thing: "who is this, which profile are they bound to, and
which session do I write through". Keeping it in a layer below both `services/` and
`mcp/` is what lets the tool surface depend on business services without the
services having to import the tool surface back.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class RunScope:
    """Identity + session for one unit of work.

    `user_id` and `profile_id` are optional at the type level because the stdio MCP
    transport builds a scope from the environment before anything has validated it.
    Every guard in `jc.authz.ownership` fails closed on a missing identity, so an
    unauthenticated scope can be constructed but cannot read or write anything.
    """

    db: AsyncSession
    user_id: str | None
    profile_id: str | None
    session_id: str | None = None
    job_id: str | None = None
    mock_session_id: str | None = None
