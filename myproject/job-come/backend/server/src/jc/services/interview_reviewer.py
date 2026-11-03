"""Runs the independent reviewer on a finished mock session, as an agent sub-task.

The reviewer is the `interview-reviewer` agent: its own role (skill, tools, model), started as a
separate run that sees the session and the profile and never the interviewer's plan. It stores its
report by calling `jc_mock_report_write`, which checks the report in the service
(`mock_report_service.write_report`). This module starts that run and reads back what it stored. It
does not call a model itself, so there is one path to a report (AGENTS-DESIGN §3 R3).
"""

from __future__ import annotations

import asyncio

from agentkit.adapters.deerflow.client import AgentRunMetadata
from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession

from jc.adapters.deerflow_client import get_deerflow_client
from jc.models.enums import MockSessionStatus
from jc.models.interview import MockSession

REVIEWER_SKILL = "interview-reviewer"
REVIEW_BUDGET_SECONDS = 180

REVIEW_MESSAGE = (
    "请评审模拟会话 mock_session_id={session_id}。"
    "用 jc_mock_session_history 读取整场问答，用 jc_profile_get 读取档案，"
    "然后调用 jc_mock_report_write 写入报告一次。不要提问，不要回复候选人。"
)


async def review_session(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    mock_session_id: str,
    budget_seconds: float = REVIEW_BUDGET_SECONDS,
) -> bool:
    """Run the reviewer on an ended session. True when it stored a report.

    The caller has already checked the session belongs to the user. A session that has not ended
    never reaches the agent. A run past its budget stores nothing and returns False.
    """
    session = await db.get(MockSession, mock_session_id)
    if session is None or session.profile_id != profile_id:
        raise PermissionError("Mock session outside this profile")
    if session.status != MockSessionStatus.COMPLETED:
        raise ValueError("a report can only be written after the session has ended")
    if session.report:
        return True

    metadata = AgentRunMetadata(
        trace_id=new_id("trc", length=16),
        user_id=user_id,
        profile_id=profile_id,
        session_id=None,
        skill_hint=REVIEWER_SKILL,
        extra={"mock_session_id": mock_session_id},
    )
    client = get_deerflow_client(db=db)
    try:
        async with asyncio.timeout(budget_seconds):
            await client.run_once(
                skill=REVIEWER_SKILL,
                metadata=metadata,
                context={"message": REVIEW_MESSAGE.format(session_id=mock_session_id)},
                db=db,
            )
    except TimeoutError:
        return False

    # The reviewer wrote through its own tool call, on another session of the database.
    await db.refresh(session)
    return bool(session.report)
