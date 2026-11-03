"""Run a subtask role: one agent run of its own, started by the service at a defined point.

A subtask role (`mode: subtask` in roles.yaml) is not a conversation and is not delegated to by a
model. The service decides when it runs: when a mock session is read for its report, when a draft is
checked before export. This module starts that run on the role's own skill, tools and model, under
the role's own time budget, and reports whether it finished in time. The result is what the run
wrote through its tools; the caller reads it back from the database.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agentkit.adapters.deerflow.client import AgentRunMetadata
from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession

from jc.adapters.deerflow_client import get_deerflow_client
from jc.agent.roles import role


async def run_subtask(
    role_id: str,
    *,
    db: AsyncSession,
    user_id: str,
    profile_id: str,
    message: str,
    extra: dict[str, Any] | None = None,
    budget_seconds: float | None = None,
) -> bool:
    """Run one subtask to its end. True when it finished inside its time budget.

    The budget is the role's `timeout_seconds` unless a caller bounds the run tighter. A run past
    its budget is cancelled and reports False. A session role is not started this way.
    """
    declared = role(role_id)
    if declared.mode != "subtask":
        raise RuntimeError(f"{role_id} is a {declared.mode} role, not a subtask")
    skill_id = declared.default_skill
    metadata = AgentRunMetadata(
        trace_id=new_id("trc", length=16),
        user_id=user_id,
        profile_id=profile_id,
        session_id=None,
        skill_hint=skill_id,
        extra=dict(extra or {}),
    )
    client = get_deerflow_client(db=db)
    try:
        async with asyncio.timeout(budget_seconds or declared.timeout_seconds):
            await client.run_once(
                skill=skill_id,
                metadata=metadata,
                context={"message": message},
                db=db,
            )
    except TimeoutError:
        return False
    return True
