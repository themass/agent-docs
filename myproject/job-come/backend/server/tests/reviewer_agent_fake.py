"""A stand-in for one run of the reviewer agent.

It calls the report tool the way the agent does: through the tool dispatcher, on its own database
session, with the identity the run was started with. A tool error ends the run without a report, as
it would for the agent, which sees the error and stops."""

from __future__ import annotations

import asyncio
from typing import Any

from jc.authz.scope import RunScope
from jc.mcp.handlers import dispatch_tool


class FakeReviewerAgent:
    def __init__(
        self,
        maker,
        *,
        report: dict[str, Any] | None = None,
        delay: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        self.maker = maker
        self.report = report
        self.delay = delay
        self.error = error
        self.runs: list[dict[str, Any]] = []
        #: What the run read with `jc_mock_session_history`: the reviewer's input, for tests.
        self.history: dict[str, Any] | None = None

    async def run_once(self, *, skill, metadata, context, db=None) -> str:
        self.runs.append({"skill": skill, "metadata": metadata, "context": context})
        await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        if self.report is None:
            return ""
        session_id = metadata.extra["mock_session_id"]
        async with self.maker() as s:
            scope = RunScope(db=s, user_id=metadata.user_id, profile_id=metadata.profile_id,
                             mock_session_id=session_id)
            # The real reviewer reads the session first, after it has ended. A history call that
            # refused an ended session left it with nothing to review, and nothing noticed because
            # this stand-in used to go straight to writing.
            self.history = await dispatch_tool(
                scope, "jc_mock_session_history", {"mock_session_id": session_id}
            )
            try:
                await dispatch_tool(scope, "jc_mock_report_write",
                                    {"mock_session_id": session_id, "report": self.report})
            except ValueError:
                pass  # the agent receives the tool error and ends its run without a report
        return ""


class FakeClientFactory:
    """Replaces get_deerflow_client in the reviewer service: every client is the same fake agent."""

    def __init__(self, agent: FakeReviewerAgent) -> None:
        self.agent = agent

    def __call__(self, db=None):
        return self.agent
