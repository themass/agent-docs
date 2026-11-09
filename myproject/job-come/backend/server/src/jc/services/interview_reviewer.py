"""Runs the independent reviewer on a finished mock session, as an agent sub-task.

The reviewer is the `interview-reviewer` agent: its own role (skill, tools, model), started as a
separate run that sees the session and the profile and never the interviewer's plan. It stores its
report by calling `jc_mock_report_write`, which checks the report in the service
(`mock_report_service.write_report`). This module starts that run and reads back what it stored. It
does not call a model itself, so there is one path to a report (AGENTS-DESIGN §3 R3).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from jc.agent.subtask import run_subtask
from jc.models.enums import MockSessionStatus
from jc.models.interview import MockSession

REVIEWER_SKILL = "interview-reviewer"

REVIEW_MESSAGE = (
    "请评审模拟会话 mock_session_id={session_id}。"
    "用 jc_mock_session_history 读取整场问答（含岗位、级别和追问），用 jc_profile_get 读取档案，"
    "然后调用 jc_mock_report_write 写入报告一次：逐题评分，并写总评 summary。"
    "不要提问，不要回复候选人。"
)


async def review_session(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    mock_session_id: str,
    budget_seconds: float | None = None,
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

    from jc.coach.role_family import family_of_session

    await run_subtask(
        REVIEWER_SKILL,
        db=db,
        user_id=user_id,
        profile_id=profile_id,
        message=REVIEW_MESSAGE.format(session_id=mock_session_id),
        extra={
            "mock_session_id": mock_session_id,
            "role_family": await family_of_session(db, session),
        },
        budget_seconds=budget_seconds,
    )
    # The reviewer wrote through its own tool call, on another session of the database, and
    # committed. This session's transaction began before that write. Under MySQL's REPEATABLE READ
    # the refresh below would read the snapshot from before it, see no report, and mark a stored
    # report as failed (live, 2026-11-08: 15 failed sessions still held a report). Ending the
    # transaction first makes the refresh read what was committed.
    await db.commit()
    await db.refresh(session)
    return bool(session.report)
