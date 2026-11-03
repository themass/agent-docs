"""Runs the independent reviewer on a finished mock session.

The reviewer is a separate model call from the interviewer. It receives the candidate's
questions and answers and the profile, and never the interviewer's plan or reasoning. Its JSON
output goes through the same checks as the tool path (`mock_report_service.write_report`), so both
routes store identical reports. The call has a wall-clock budget; on timeout nothing is written and
the caller decides what to show.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from jc.authz.ownership import require_owned_profile
from jc.authz.scope import RunScope
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.services.mock_report_service import (
    profile_payload_text,
    session_transcript,
    write_report,
)
from jc.stores.interview_store import InterviewStore

REVIEW_BUDGET_SECONDS = 180

REVIEWER_INSTRUCTIONS = """You are the independent reviewer of a finished mock interview. You are a
spectator: you never ask questions and never see the interviewer's reasoning.

Return one JSON object: {"questions": [...]}. For each question give:
- "question_id": copied from the input.
- "scores": integers 1-10 for structure, relevance, depth, communication, reflection; null where the
  answer gives no evidence. Anchors: 3 = weak, 6 = adequate, 9 = strong, interpolate by evidence.
- "evidence": for each score, a short quote copied word-for-word from the candidate's own answer.
- "praise": one sentence on what the answer did well.
- "fixes": [{"severity": "must" | "suggest" | "nit", "text": "..."}], each naming the exact
  sentence, why it is inaccurate or missing, and a suggested wording.
- "reference": [{"text": "...", "source": "..."}] where source is a phrase copied from the profile.
Do not compute averages."""


async def run_review(
    scope: RunScope,
    *,
    mock_session_id: str,
    budget_seconds: float = REVIEW_BUDGET_SECONDS,
) -> dict[str, Any]:
    """Score a completed session with the reviewer model and store the validated report."""
    await require_owned_profile(scope)
    store = InterviewStore(scope.db)
    session = await store.get_mock_session(mock_session_id)
    if session is None or session.profile_id != scope.profile_id:
        raise PermissionError("Mock session outside this profile")
    if session.status != "completed":
        # Checked before the model call, so an unfinished session costs nothing.
        raise ValueError("a report can only be written after the session has ended")

    transcript = await session_transcript(store, session)
    profile_text = await profile_payload_text(scope)
    payload = {"transcript": transcript, "profile": json.loads(profile_text)}

    router = get_llm_router()

    def validate(response: Any) -> dict[str, Any]:
        data = json.loads(router.content_from_response(response))
        if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
            raise ValueError("invalid review contract")
        return data

    async with asyncio.timeout(budget_seconds):
        raw = await router.acompletion(
            "reviewer",
            log_context=llm_context("interview_reviewer"),
            messages=[
                {"role": "system", "content": REVIEWER_INSTRUCTIONS},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            response_validator=validate,
        )

    return await write_report(scope, mock_session_id=mock_session_id, raw=raw)
