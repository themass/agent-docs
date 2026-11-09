"""A stored mock interview, turned into what the acceptance checklist reads.

`jc.coach.acceptance` checks a list of events. To check a real interview (run against a real model
in a test environment) the events have to come out of what the server stored. This does that, and
says what it could not read instead of guessing:

- the candidate's own words are in the ledger inside the task text wrapped around them
  (`wrap_coach_mock_message`), and are taken back out;
- a tool call and its result are stored as two rows; they become one event carrying the verdict
  (`accepted`, `code`). A result goes to the nearest call of that tool still waiting for one, so a
  result that was never stored does not hand its neighbour's verdict to the wrong call. The ledger
  keeps no call id, so two calls of the same tool in flight at once cannot be told apart; the
  interviewer registers one question at a time and this does not arise for it;
- anything it cannot place goes into `warnings`, which a person reads before trusting the result.

The shapes of what a live run stores have been read from the code that writes them and checked
on rows built the same way. They have not been seen on a live run: the first real run may show
a result format this does not read, and `warnings` is where that will appear.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.coach.acceptance import Finding
from jc.coach.role_family import family_of_session
from jc.models.agent_trace import AgentTrace
from jc.models.interview import MockSession
from jc.services.mock_answer_recorder import is_steering_message
from jc.services.mock_report_service import answers_by_main_question, session_transcript
from jc.stores.interview_store import InterviewStore

Event = dict[str, Any]

#: The last line of the task text; the candidate's words come after it.
_MARKER = "用户原话：\n"
#: Arguments the identity layer fills in; the model never wrote them, so they are not shown.
_IDENTITY_ARGS = frozenset({"mock_session_id", "jc_user_id", "jc_profile_id", "jc_session_id",
                            "jc_job_id", "jc_mock_session_id"})


def unwrap_candidate_text(text: str) -> str:
    """What the candidate typed, out of the task text the server wrapped around it.

    The wrapper ends with the marker, then their words, then one newline. The marker is in the
    wrapper once, so it is the first one: a candidate who types it on a line of their own must not
    have their words cut there. A message that was never wrapped comes back as it is."""
    index = text.find(_MARKER)
    if index < 0:
        return text
    body = text[index + len(_MARKER):]
    return body[:-1] if body.endswith("\n") else body


def _parse_result(raw: Any) -> dict[str, Any] | None:
    """The dict a tool returned, from the string the ledger holds. Some runtimes wrap a tool's
    output in a list of content blocks; those are opened. None when it is neither."""
    value = raw
    for _ in range(3):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return None
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            texts = [
                b.get("text") for b in value
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            if not texts:
                return None
            value = texts[0]
            continue
        return None
    return None


def corrections_from_trace(rows: Sequence[AgentTrace]) -> dict[str, int]:
    """How many interview replies were tried for one question, and how many of those failed to
    come back with one. Written by the agent service as `interview_reply_corrected` rows."""
    counts = {"corrected": 0, "kept_first": 0}
    for row in rows:
        if row.event_type == "interview_reply_corrected":
            outcome = (row.payload or {}).get("outcome")
            if outcome in counts:
                counts[outcome] += 1
    return counts


def events_from_trace(rows: Sequence[AgentTrace]) -> tuple[list[Event], list[str]]:
    """The checklist's events for one session's ledger rows, and what could not be read."""
    events: list[Event] = []
    warnings: list[str] = []
    open_calls: dict[str | None, list[Event]] = {}
    for row in sorted(rows, key=lambda r: r.seq):
        payload = row.payload or {}
        if row.event_type == "user_message":
            said = unwrap_candidate_text(payload.get("text", ""))
            events.append({"role": "candidate", "text": said})
        elif row.event_type == "assistant_message":
            events.append({"role": "interviewer", "text": payload.get("text", "")})
        elif row.event_type == "tool_call":
            name = payload.get("name")
            arguments = {k: v for k, v in (payload.get("arguments") or {}).items()
                         if k not in _IDENTITY_ARGS}
            event: Event = {"role": "tool", "tool": name, "arguments": arguments, "accepted": True}
            events.append(event)
            open_calls.setdefault(name, []).append(event)
        elif row.event_type == "tool_result":
            name = payload.get("name")
            waiting = open_calls.get(name) or []
            if not waiting:
                warnings.append(f"{name} 的结果找不到对应的调用，已忽略")
                continue
            event = waiting.pop()
            parsed = _parse_result(payload.get("result"))
            if parsed is None:
                shown = str(payload.get("result"))[:60]
                warnings.append(f"{name} 的结果读不出来，按“已通过”处理：{shown}")
                continue
            if "accepted" in parsed:
                event["accepted"] = bool(parsed["accepted"])
            if parsed.get("code"):
                event["code"] = parsed["code"]
    for name, waiting in open_calls.items():
        warnings.extend(f"{name} 的调用没有结果，按“已通过”处理" for _ in waiting)
    return events, warnings


async def record_interview(db: AsyncSession, mock_session_id: str) -> dict[str, Any]:
    """Everything the checklist needs about one stored interview, as plain JSON-able data."""
    session = await db.get(MockSession, mock_session_id)
    if session is None:
        raise LookupError(f"没有这场面试：{mock_session_id}")

    rows = list((await db.execute(
        select(AgentTrace).where(AgentTrace.mock_session_id == mock_session_id)
    )).scalars().all())
    events, warnings = events_from_trace(rows)
    if not events:
        warnings.append("没有对话记录：这场面试没有留下可检查的消息（追踪账本里没有这场的行）")

    store = InterviewStore(db)
    transcript = await session_transcript(store, session)
    answers = answers_by_main_question(transcript)
    candidate_lines = [e["text"] for e in events if e["role"] == "candidate"]
    job = None
    company = None
    if session.job_id:
        from jc.models.job import Job

        found = await db.get(Job, session.job_id)
        if found is not None and found.profile_id == session.profile_id:
            job = found.title
            company = found.company or None

    return {
        "session": {
            "id": session.id, "style": session.style, "level": session.level, "job": job,
            "status": session.status, "report_status": session.report_status,
            "ended_reason": (session.coverage or {}).get("ended_reason"),
        },
        "role_family": await family_of_session(db, session),
        "events": events,
        "corrections": corrections_from_trace(rows),
        "answers": answers,
        "skipped": [t["question_id"] for t in transcript if t.get("skipped")],
        "control_messages": [t for t in candidate_lines if is_steering_message(t)],
        "company": company,
        "report": session.report,
        "warnings": warnings,
    }


_LABEL = {True: "通过", False: "未通过"}


def render_findings(*groups: Sequence[Finding]) -> str:
    """The checklist's findings as text a person reads. Failures first, then the rules that need a
    person to read the interview, then what passed."""
    findings = [f for group in groups for f in group]
    failed = [f for f in findings if not f.ok and not f.needs_a_person]
    manual = [f for f in findings if f.needs_a_person]
    passed = [f for f in findings if f.ok and not f.needs_a_person]
    lines: list[str] = []
    if failed:
        lines.append(f"未通过（{len(failed)}）")
        lines += [f"  ✗ {f.check}" + (f"：{f.detail}" if f.detail else "") for f in failed]
    if manual:
        lines.append(f"需要人来读（{len(manual)}）")
        lines += [f"  ? {f.check}：{f.detail}" for f in manual]
    lines.append(f"通过（{len(passed)}）")
    lines += [f"  ✓ {f.check}" for f in passed]
    return "\n".join(lines)
