"""The interviewer's guards: plan (read), ask, and end.

Rules live here, not in the prompt. A refused call returns `accepted: False` with a reason and
writes nothing, so the interviewer can read the gap and keep going. The limits follow the session:
a counted full run allows 20 main questions and 2 follow-ups per main question; a warm-up allows 5
and 1 (SPEC-MOCK-INTERVIEW §2). Review is `interview_reviewer.run_review`, which requires the
session to have ended.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

from jc.authz.ownership import require_owned_profile
from jc.authz.scope import RunScope
from jc.coach.coverage import coverage_of
from jc.models.enums import MAX_REPORT_RUNS, MockReportStatus, MockSessionStatus
from jc.models.interview import MockSession
from jc.models.job import Job
from jc.stores.interview_store import InterviewStore

FULL_MAIN, FULL_FOLLOWUPS = 20, 2
WARMUP_MAIN, WARMUP_FOLLOWUPS = 5, 1
END_REASONS = ("completed", "user_ended")
#: An active session with no new question for this long is ended as "timeout" and reported as
#: unfinished (SPEC-MOCK-INTERVIEW §5). Activity is the last question asked, or the start.
IDLE_LIMIT = timedelta(hours=24)
#: How many times a candidate may ask for a different question in one session
#: (SPEC-MOCK-INTERVIEW §5).
SWAP_LIMIT = 3

#: The stages an interview moves through (SPEC-MOCK-INTERVIEW-V2 §3.1). Only the first three are
#: stages a question is asked in; the candidate's own turn has a tool of its own.
ASKING_STAGES = ("experience", "core", "scenario")
STAGES = ("opening", *ASKING_STAGES, "candidate_qa", "closing")
#: Where in the run of main questions each asking stage ends, as a share of the limit.
_STAGE_ENDS = (("experience", 0.25), ("core", 0.70), ("scenario", 1.0))
#: A question the interviewer makes up is held to this.
MAX_STEM_CHARS = 200
#: Two questions whose character bigrams overlap this much are the same question in other words.
SIMILAR_STEM = 0.6


def limits(session: MockSession) -> tuple[int, int]:
    """(main questions, follow-ups per main question) allowed for this session."""
    if session.quota_counted:
        return FULL_MAIN, FULL_FOLLOWUPS
    return WARMUP_MAIN, WARMUP_FOLLOWUPS


def _state(session: MockSession) -> dict[str, Any]:
    # A deep copy: appending to a shared nested list would change the loaded value too, and
    # SQLAlchemy would see no change to write.
    state = copy.deepcopy(session.coverage or {})
    state.setdefault("asked", [])
    state.setdefault("ended_reason", None)
    state.setdefault("ended_early", False)
    return state


def _words(text: str) -> str:
    """A question's text without spacing or punctuation, for telling whether two are the same."""
    return "".join(ch for ch in text if ch.isalnum())


def _bigrams(text: str) -> set[str]:
    words = _words(text)
    return {words[i:i + 2] for i in range(len(words) - 1)} or {words}


def similarity(a: str, b: str) -> float:
    left, right = _bigrams(a), _bigrams(b)
    return len(left & right) / len(left | right) if left and right else 0.0


def suggested_stage(asked_main: int, main_limit: int) -> str:
    """The stage the next question belongs to, by how far through the questions the interview is.

    A suggestion: the interviewer may follow the candidate's answers somewhere else."""
    if asked_main >= main_limit:
        return "candidate_qa"
    share = asked_main / main_limit
    return next(stage for stage, end in _STAGE_ENDS if share < end)


def _naive_utc(moment: datetime) -> datetime:
    """The UTCDateTime column reads back naive UTC; keep every comparison on that footing."""
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo else moment


def _close(session: MockSession, state: dict[str, Any], *, reason: str) -> None:
    session.status = MockSessionStatus.COMPLETED
    session.completed_at = datetime.now(UTC)
    state["ended_reason"] = reason
    state["ended_early"] = reason in ("user_ended", "timeout")
    session.coverage = state
    if state["asked"]:
        session.report_status = MockReportStatus.QUEUED
    else:
        # Ended before the first question: a review of nothing can only fail, so it is not run.
        session.report_status = MockReportStatus.FAILED
        session.report_attempts = MAX_REPORT_RUNS
        session.report_error = "这场面试没有提问，没有可评审的内容。"


async def _owned_session(scope: RunScope, mock_session_id: str) -> MockSession:
    await require_owned_profile(scope)
    session = await InterviewStore(scope.db).get_mock_session(mock_session_id)
    if session is None or session.profile_id != scope.profile_id:
        raise PermissionError("Mock session outside this profile")
    state = _state(session)
    if session.status == MockSessionStatus.ACTIVE:
        last = state.get("last_activity")
        last_at = datetime.fromisoformat(last) if last else _naive_utc(session.started_at)
        if datetime.now(UTC).replace(tzinfo=None) - last_at > IDLE_LIMIT:
            _close(session, state, reason="timeout")
            await scope.db.commit()
    return session


async def current_session(scope: RunScope, mock_session_id: str) -> MockSession:
    """The session as it stands now: one left idle past the limit is closed first, so a caller never
    resumes an interview that has already timed out."""
    return await _owned_session(scope, mock_session_id)


async def must_have_of(scope: RunScope, session: MockSession) -> list[str]:
    if not session.job_id:
        return []
    job = await scope.db.get(Job, session.job_id)
    if job is None:
        return []
    return [str(item) for item in (job.requirements or {}).get("must_have_skills") or []]


async def _asked_stems(store: InterviewStore, asked: list[dict[str, Any]]) -> list[str]:
    """Stems of the questions that were actually put. A skipped question covers nothing."""
    stems = []
    for entry in asked:
        if entry.get("skipped"):
            continue
        question = await store.get_question(entry["question_id"])
        if question is not None:
            stems.append(question.stem)
    return stems


def question_label(asked: list[dict[str, Any]]) -> str:
    """The label the candidate sees for the newest question: "第 3 题" or "第 3 题 · 追问 1".
    Skipped questions keep their number, so the numbering matches what the candidate was shown."""
    mains = [a for a in asked if a["kind"] == "main"]
    last = asked[-1]
    if last["kind"] == "main":
        return f"第 {len(mains)} 题"
    parent = last.get("parent_question_id")
    index = next(i for i, a in enumerate(mains) if a["question_id"] == parent) + 1
    follow = sum(1 for a in asked if a["kind"] == "followup"
                 and a.get("parent_question_id") == parent)
    return f"第 {index} 题 · 追问 {follow}"


def _refuse(reason: str, **extra: Any) -> dict[str, Any]:
    return {"accepted": False, "reason": reason, **extra}


async def _open_question(
    store: InterviewStore, asked: list[dict[str, Any]], mock_session_id: str
) -> str | None:
    """The question on the table: the last one asked, not skipped, with no answer yet in this
    session."""
    if not asked:
        return None
    last = asked[-1]
    if last.get("skipped"):
        return None
    if await store.get_latest_attempt_in_session(last["question_id"], mock_session_id) is not None:
        return None
    return last["question_id"]


async def plan(scope: RunScope, *, mock_session_id: str) -> dict[str, Any]:
    """A map of the session. It suggests; it does not force the next question."""
    session = await _owned_session(scope, mock_session_id)
    store = InterviewStore(scope.db)
    state = _state(session)
    asked = state["asked"]
    main_limit, _ = limits(session)
    mains = [a for a in asked if a["kind"] == "main"]
    must = await must_have_of(scope, session)
    coverage = coverage_of(must, await _asked_stems(store, asked))
    followups: dict[str, int] = {}
    for entry in asked:
        if entry["kind"] == "followup":
            parent = entry.get("parent_question_id") or ""
            followups[parent] = followups.get(parent, 0) + 1
    candidate_qa = bool(state.get("candidate_qa"))
    stage_counts: dict[str, int] = {}
    for entry in mains:
        if entry.get("stage"):
            stage_counts[entry["stage"]] = stage_counts.get(entry["stage"], 0) + 1
    if candidate_qa:
        stage, suggested = "candidate_qa", "closing"
    elif not asked:
        stage, suggested = "opening", suggested_stage(0, main_limit)
    else:
        suggested = suggested_stage(len(mains), main_limit)
        last_main = mains[-1] if mains else None
        stage = (last_main or {}).get("stage") or suggested_stage(
            max(0, len(mains) - 1), main_limit
        )
    return {
        "style": session.style,
        "status": session.status,
        "stage": stage,
        "suggested_stage": suggested,
        "stage_counts": stage_counts,
        "candidate_qa": candidate_qa,
        "asked_main": len(mains),
        "main_limit": main_limit,
        "remaining_main": max(0, main_limit - len(mains)),
        "followups_by_parent": followups,
        "must_have": must,
        "covered": coverage.covered,
        "uncovered": coverage.missing,
        "suggested_next": coverage.missing[0] if coverage.missing else None,
        "current_question_id": (
            None if candidate_qa else await _open_question(store, asked, session.id)
        ),
        "skipped": sum(1 for a in asked if a.get("skipped")),
        "swaps_left": max(0, SWAP_LIMIT - int(state.get("swaps", 0))),
    }


async def _current_for_action(
    scope: RunScope, session: MockSession, state: dict[str, Any], question_id: str
) -> dict[str, Any] | None:
    """Skip and swap act only on the question on the table. Returns a refusal, or None."""
    if session.status != MockSessionStatus.ACTIVE:
        return _refuse("这场模拟面试已经结束。", code="session_closed")
    store = InterviewStore(scope.db)
    if await _open_question(store, state["asked"], session.id) != question_id:
        return _refuse("只能对当前这道题操作。", code="not_current")
    return None


async def skip(scope: RunScope, *, mock_session_id: str, question_id: str) -> dict[str, Any]:
    """The candidate skips the question on the table. It stays in the session as unanswered."""
    session = await _owned_session(scope, mock_session_id)
    state = _state(session)
    refusal = await _current_for_action(scope, session, state, question_id)
    if refusal:
        return refusal
    for entry in state["asked"]:
        if entry["question_id"] == question_id:
            entry["skipped"] = True
    state["last_activity"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
    session.coverage = state
    await scope.db.commit()
    return {"accepted": True}


async def swap(scope: RunScope, *, mock_session_id: str, question_id: str) -> dict[str, Any]:
    """The candidate asks for a different question. The question on the table is taken back out of
    the session, so it neither counts nor covers anything. Limited to SWAP_LIMIT per session."""
    session = await _owned_session(scope, mock_session_id)
    state = _state(session)
    refusal = await _current_for_action(scope, session, state, question_id)
    if refusal:
        return refusal
    if int(state.get("swaps", 0)) >= SWAP_LIMIT:
        return _refuse(f"换题已用完（最多 {SWAP_LIMIT} 次）。", code="swap_limit")
    state["asked"] = [a for a in state["asked"] if a["question_id"] != question_id]
    # Nothing is on the table until the next question is asked: the last entry left in `asked` is an
    # earlier question, and the candidate's next words are not an addition to its answer.
    state["table_closed"] = True
    state["swaps"] = int(state.get("swaps", 0)) + 1
    state["last_activity"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
    session.coverage = state
    qids = [q for q in (session.question_ids or []) if q != question_id]
    session.question_ids = qids
    await scope.db.commit()
    return {"accepted": True, "swaps_left": SWAP_LIMIT - state["swaps"]}


async def ask(
    scope: RunScope,
    *,
    mock_session_id: str,
    question_id: str | None = None,
    stem: str | None = None,
    question_type: str = "behavioral",
    tags: list[str] | None = None,
    kind: str = "main",
    parent_question_id: str | None = None,
    experience: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """Register a question the interviewer is about to put.

    The question is either one already in the bank (`question_id`) or a new one given as `stem`,
    which is created, or found by its text, in this same call. A refusal writes nothing: a question
    created for a refused ask is rolled back with it.
    """
    if kind not in ("main", "followup"):
        raise ValueError("kind must be 'main' or 'followup'")
    if bool(question_id) == bool(stem and stem.strip()):
        raise ValueError("give exactly one of question_id or stem")
    if stage is not None and stage not in ASKING_STAGES:
        raise ValueError(f"stage must be one of {ASKING_STAGES} (the candidate's turn is opened "
                         "with jc_mock_open_qa), got " + repr(stage))
    session = await _owned_session(scope, mock_session_id)
    if session.status != MockSessionStatus.ACTIVE:
        return _refuse("这场模拟面试已经结束。", code="session_closed")

    state = _state(session)
    asked = state["asked"]
    if state.get("candidate_qa"):
        return _refuse("已经进入候选人提问环节，不再出新题；请回答候选人的问题，然后结束面试。",
                       code="candidate_qa_open")
    main_limit, followup_limit = limits(session)
    mains = [a for a in asked if a["kind"] == "main"]
    if kind == "main":
        if len(mains) >= main_limit:
            return _refuse(f"主问题已达 {main_limit} 个，请结束场次。", code="main_limit")
        parent = None
    else:
        parent = parent_question_id
        if not any(a["question_id"] == parent and a["kind"] == "main" for a in asked):
            return _refuse("追问必须针对本场已问过的主问题。", code="parent_not_asked")
        used = sum(
            1 for a in asked
            if a["kind"] == "followup" and a.get("parent_question_id") == parent
        )
        if used >= followup_limit:
            return _refuse(f"这道题的追问已达 {followup_limit} 次，请换下一个主问题。",
                           code="followup_limit")

    store = InterviewStore(scope.db)
    if question_id:
        question = await store.get_question(question_id)
        if question is None or question.profile_id != scope.profile_id:
            raise ValueError("question is not in this profile")
    else:
        # A question the interviewer makes up is checked before it is written anywhere.
        text = (stem or "").strip()
        if len(text) > MAX_STEM_CHARS:
            return _refuse(f"题干太长（{len(text)} 字，最多 {MAX_STEM_CHARS} 字）。"
                           "面试官一次只问一个具体的问题，请缩短。", code="stem_too_long")
        asked_stems = await _asked_stems(store, asked)
        for earlier in asked_stems:
            if _words(earlier) == _words(text):
                return _refuse("这道题已经问过。", code="already_asked")
        if kind == "main":
            for earlier in asked_stems:
                if similarity(earlier, text) >= SIMILAR_STEM:
                    return _refuse(
                        f"这道题和已经问过的“{earlier}”几乎是同一个问题，请换一个角度或一个新话题。",
                        code="too_similar")
        from jc.services.question_bank_service import question_upsert

        upserted = await question_upsert(
            scope, stem=stem, question_type=question_type, tags=tags, job_id=session.job_id,
            mock_session_id=mock_session_id, commit=False,
        )
        question_id = upserted["id"]
    if any(entry["question_id"] == question_id for entry in asked):
        await scope.db.rollback()
        return _refuse("这道题已经问过。", code="already_asked")

    entry = {
        "question_id": question_id,
        "kind": kind,
        "parent_question_id": parent,
        "experience": experience,
    }
    if stage and kind == "main":
        entry["stage"] = stage
    asked.append(entry)
    state.pop("table_closed", None)
    state["last_activity"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
    session.coverage = state
    qids = list(session.question_ids or [])
    if question_id not in qids:
        qids.append(question_id)
        session.question_ids = qids
    await scope.db.commit()
    remaining = main_limit - len(mains) - (1 if kind == "main" else 0)
    return {"accepted": True, "question_id": question_id,
            "asked_main": len(mains) + (1 if kind == "main" else 0),
            "remaining_main": max(0, remaining), "label": question_label(asked)}


def _not_ready_to_wrap_up(
    state: dict[str, Any], session: MockSession, coverage: Any
) -> dict[str, Any] | None:
    """The refusal for an interview that has not asked enough yet, or None.

    Shared by the candidate's turn and by ending as completed, so neither can be reached by
    skipping the other."""
    mains = [a for a in state["asked"] if a["kind"] == "main"]
    main_limit, _ = limits(session)
    if not mains:
        return _refuse("还没有问过任何题，不能进入候选人提问环节。", code="not_started")
    if len(mains) < main_limit and coverage.missing:
        return _refuse(
            "题数不足且还有必备项没有问到，请继续提问。",
            code="uncovered",
            asked_main=len(mains),
            main_limit=main_limit,
            uncovered=coverage.missing,
        )
    return None


async def open_qa(scope: RunScope, *, mock_session_id: str) -> dict[str, Any]:
    """Give the floor to the candidate: they may now ask the interviewer questions.

    The candidate's own questions are not answers to anything, so from here nothing they say is
    recorded as one and the interviewer asks no more questions. An interview ends as completed only
    after this. Opening it again is harmless."""
    session = await _owned_session(scope, mock_session_id)
    if session.status != MockSessionStatus.ACTIVE:
        return _refuse("这场模拟面试已经结束。", code="session_closed")
    state = _state(session)
    if state.get("candidate_qa"):
        return {"accepted": True, "already_open": True}
    must = await must_have_of(scope, session)
    coverage = coverage_of(must, await _asked_stems(InterviewStore(scope.db), state["asked"]))
    refusal = _not_ready_to_wrap_up(state, session, coverage)
    if refusal:
        return refusal
    state["candidate_qa"] = True
    state["table_closed"] = True
    state["last_activity"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
    session.coverage = state
    await scope.db.commit()
    return {"accepted": True, "already_open": False}


async def end(
    scope: RunScope, *, mock_session_id: str, reason: str = "completed"
) -> dict[str, Any]:
    if reason not in END_REASONS:
        raise ValueError(f"reason must be one of {END_REASONS}")
    session = await _owned_session(scope, mock_session_id)
    if session.status != MockSessionStatus.ACTIVE:
        return _refuse("这场模拟面试已经结束。", code="session_closed")

    state = _state(session)
    asked = state["asked"]
    main_limit, _ = limits(session)
    mains = [a for a in asked if a["kind"] == "main"]
    must = await must_have_of(scope, session)
    coverage = coverage_of(must, await _asked_stems(InterviewStore(scope.db), asked))

    if reason == "completed":
        refusal = _not_ready_to_wrap_up(state, session, coverage)
        if refusal:
            return refusal
        if not state.get("candidate_qa"):
            return _refuse(
                "候选人还没有提问的机会。先调用 jc_mock_open_qa 问一句“你有什么想问我的吗”，"
                "回答完候选人的问题，再结束面试。",
                code="candidate_qa_not_opened",
            )

    _close(session, state, reason=reason)
    await scope.db.commit()
    return {"accepted": True, "status": MockSessionStatus.COMPLETED.value,
            "asked_main": len(mains), "ended_early": state["ended_early"]}
