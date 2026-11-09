"""One turn of a mock interview, decided by the server (ADR-007).

The server reads the session's recorded state, decides the next step (`mock_flow.decide`), and
writes what the candidate sees from that state. The model is called for two checked jobs only:
judging whether an answer needs a follow-up, and wording a chosen main question. Its output is used
only when it passes the checks in `mock_flow`; otherwise the server uses the bank's own text.

`run_turn` returns the text to show, or None when this turn belongs to the model: after the
candidate's own questions have opened, the model answers them and nothing here is recorded.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agentkit.common.ids import new_id
from sqlalchemy.ext.asyncio import AsyncSession

from jc.agent.single import run_single
from jc.authz.scope import RunScope
from jc.coach.coverage import Candidate, coverage_of, key_terms, question_match_text
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.models.enums import MockSessionStatus, QuestionSource
from jc.models.interview import InterviewQuestion
from jc.models.job import Job
from jc.services import mock_guard_service as guard
from jc.services.interview_reply import refers_to_earlier_talk
from jc.services.mock_answer_recorder import is_steering_message
from jc.services.mock_flow import (
    Action,
    FlowState,
    Turn,
    check_followup,
    check_phrasing,
    decide,
)
from jc.services.mock_opening import opening_text
from jc.stores.interview_store import InterviewStore

logger = logging.getLogger(__name__)

MOCK_FLOW_SKILL = "mock-flow"
#: A checked job is short. A call that is still running after this falls back to the server's text.
MODEL_TIMEOUT_SEC = 20

REFER_TEXT = "这个我需要和团队确认后再回复你。"
MAX_ANSWER_CHARS = 200
NO_QUESTIONS_TEXT = "这个岗位暂时没有可以问的题，这场面试先到这里。"
CLOSING_TEXT = "今天的面试就到这里，谢谢你的时间。这场面试的报告可以在“面试归档”里查看。"
QA_OPEN_TEXT = "我的问题都问完了。你有什么想问我的吗？"
AFTER_INTRO_TEXT = "好，谢谢你的介绍。"
SKIP_TEXT = "好，我们换一题。"

_END = re.compile(r"结束|终止|停止")
_SKIP = re.compile(r"下一|换一|换个|跳过")


def _load(row: Any) -> dict[str, Any]:
    return dict(row.coverage or {})


async def _save(db: AsyncSession, row: Any, **updates: Any) -> None:
    # Read the stored value again: the guards commit their own changes to the same row.
    current = dict(row.coverage or {})
    current.update(updates)
    row.coverage = current
    await db.flush()
    await db.commit()


def _flow_state(row: Any, state: dict[str, Any], main_limit: int, followup_limit: int) -> FlowState:
    return FlowState(
        opening_sent=bool(state.get("opening_sent")),
        intro_done=bool(state.get("intro_done")),
        asked=tuple(
            Turn(a["question_id"], a["kind"], a.get("parent_question_id"))
            for a in state.get("asked") or []
        ),
        answered=int(state.get("answered_upto") or 0),
        closed_mains=frozenset(state.get("closed_mains") or []),
        candidate_qa=bool(state.get("candidate_qa")),
        ended=row.status != MockSessionStatus.ACTIVE,
        main_limit=main_limit,
        followup_limit=followup_limit,
    )


async def _bank(store: InterviewStore, profile_id: str, job_id: str | None) -> list[Candidate]:
    """The questions this job can be asked: its own bank only. Another job's questions are never
    put to this candidate, so an empty pool is filled by `_fill_pool`, not borrowed."""
    if not job_id:
        return []
    questions = await store.search_questions(profile_id, job_id=job_id, limit=200)
    # A bank question that points back at an earlier answer cannot stand as a main question. It is
    # never offered: the guard would refuse it, and the interview would stall on it.
    return [
        Candidate(question_id=q.id, stem=question_match_text(q.stem, q.tags))
        for q in questions
        if not refers_to_earlier_talk(q.stem)
    ]


async def _stem_for(requirement: str, job_title: str | None, job_text: str | None) -> str | None:
    """A main question for one must-have, written by the model and checked. None when it fails."""
    data = await _model_json(
        MOCK_FLOW_SKILL,
        {"task": "stem", "requirement": requirement, "job_title": job_title or "",
         "job_text": (job_text or "")[:1500]},
        "mock_flow_stem",
    )
    text = (data or {}).get("question") if data else None
    if not isinstance(text, str):
        return None
    text = text.strip()
    check = check_phrasing(requirement, text)
    if not check.ok or not (key_terms(requirement) & key_terms(text)):
        logger.info("generated stem refused: %s", check.reason or "no_key_term")
        return None
    return text


async def _fill_pool(
    db: AsyncSession, store: InterviewStore, row: Any, profile_id: str, must: list[str],
    pool: list[Candidate],
) -> list[Candidate]:
    """For each must-have the job's bank does not cover, write one main question for it into the
    job's bank (source mock, tagged with the requirement). The next session finds it there."""
    if not row.job_id or not must:
        return pool
    covered = coverage_of(must, [c.stem for c in pool]).covered
    job = await db.get(Job, row.job_id)
    added = list(pool)
    for requirement in must:
        if requirement in covered:
            continue
        stem = await _stem_for(requirement, job.title if job else None,
                               job.raw_text if job else None)
        if stem is None:
            continue
        question = InterviewQuestion(
            id=new_id("iq"), profile_id=profile_id, job_id=row.job_id, stem=stem,
            question_type="behavioral", source=QuestionSource.MOCK, tags=[requirement],
        )
        await store.create_question(question)
        added.append(Candidate(question_id=question.id,
                               stem=question_match_text(stem, [requirement])))
    await db.flush()
    return added


async def _model_json(skill_id: str, payload: dict[str, Any], caller: str) -> dict[str, Any] | None:
    """One model call for a checked job. None when the model did not return a JSON object."""
    try:
        raw = await run_single(
            skill_id,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout_seconds=MODEL_TIMEOUT_SEC,
            log_context=llm_context(caller),
        )
        data = json.loads(get_llm_router().content_from_response(raw))
    except Exception:  # noqa: BLE001 - the server's own text is the fallback
        logger.warning("%s: model call failed; using the server's text", caller, exc_info=True)
        return None
    return data if isinstance(data, dict) else None


async def _phrase(stem: str) -> str:
    """The main question as the candidate reads it. The bank's wording when the model's fails."""
    data = await _model_json(
        MOCK_FLOW_SKILL, {"task": "phrase", "question": stem}, "mock_flow_phrase",
    )
    wording = (data or {}).get("question") if data else None
    if isinstance(wording, str) and check_phrasing(stem, wording).ok:
        return wording.strip()
    return stem


async def _answer_candidate(db: AsyncSession, row: Any, question: str) -> str:
    """The candidate's question, answered from the job's own text. The model answers in one short
    statement, checked: no question back to the candidate, not too long. Anything it cannot answer
    from the job description is referred to the team."""
    job = await db.get(Job, row.job_id) if row.job_id else None
    data = await _model_json(
        MOCK_FLOW_SKILL,
        {"task": "answer", "question": question[:300],
         "job_title": job.title if job else "", "job_text": (job.raw_text if job else "")[:1500]},
        "mock_flow_answer",
    )
    text = (data or {}).get("answer") if data else None
    if isinstance(text, str):
        text = text.strip()
        if text and len(text) <= MAX_ANSWER_CHARS and "？" not in text and "?" not in text:
            return text
    logger.info("candidate question answered by the server's fallback")
    return REFER_TEXT


async def _judge_followup(main_stem: str, answer: str, followups: int) -> str | None:
    """The follow-up question for this answer, or None when no follow-up is needed or the model's
    judgement does not pass its checks."""
    data = await _model_json(
        MOCK_FLOW_SKILL,
        {"task": "followup", "main_question": main_stem, "candidate_answer": answer,
         "followups_so_far": followups},
        "mock_flow_followup",
    )
    if data is None:
        return None
    check = check_followup(data, answer)
    if not check.ok:
        logger.info("follow-up refused by the server: %s", check.reason)
        return None
    if not data.get("followup"):
        return None
    return str(data["question"]).strip()


async def run_turn(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    mock_session_id: str,
    text: str,
    answered: bool,
) -> str | None:
    """The reply to one candidate message in a mock interview, or None when the model replies.

    `answered` is whether the message was recorded as the answer to the question on the table (see
    `record_mock_answer`)."""
    store = InterviewStore(db)
    row = await store.get_mock_session(mock_session_id)
    if row is None or row.profile_id != profile_id:
        return None
    scope = RunScope(db=db, user_id=user_id, profile_id=profile_id, mock_session_id=mock_session_id)

    if row.status == MockSessionStatus.ACTIVE and is_steering_message(text) and _END.search(text):
        await guard.end(scope, mock_session_id=mock_session_id, reason="user_ended")
        return CLOSING_TEXT
    state = _load(row)
    if state.get("candidate_qa") and row.status == MockSessionStatus.ACTIVE:
        # The candidate's turn. Their words are not an answer; they may ask about the job. A
        # steering word here ("下一题") has nothing to skip, so the interview closes.
        if is_steering_message(text):
            await guard.end(scope, mock_session_id=mock_session_id, reason="completed")
            return CLOSING_TEXT
        return await _answer_candidate(db, row, text)
    if row.status != MockSessionStatus.ACTIVE:
        return CLOSING_TEXT

    if not state.get("opening_sent"):
        job = await db.get(Job, row.job_id) if row.job_id else None
        opening = opening_text(job.company if job else None, job.title if job else None)
        await _save(db, row, opening_sent=True, opening_text=opening)
        return opening

    just_introduced = False
    if not state.get("intro_done"):
        # The first message after the opening is the self-introduction: nothing is recorded for it.
        await _save(db, row, intro_done=True)
        just_introduced = True
        state = _load(row)

    steering = is_steering_message(text)
    wants_skip = bool(state.get("asked")) and steering and bool(_SKIP.search(text))
    if wants_skip and not answered:
        on_table = state["asked"][-1]
        await guard.skip(
            scope, mock_session_id=mock_session_id, question_id=on_table["question_id"],
        )
        closed = list(state.get("closed_mains") or [])
        # Skipping a main, or a follow-up on it, moves on from that main: it is not followed up.
        main_id = on_table["question_id"] if on_table["kind"] == "main" else on_table.get(
            "parent_question_id")
        if main_id:
            closed.append(main_id)
        await _save(db, row, answered_upto=len(state["asked"]), closed_mains=closed)
        state = _load(row)
        answered = True
        last_skip = True
    else:
        last_skip = False

    if answered and state.get("asked"):
        await _save(db, row, answered_upto=len(state["asked"]))
        state = _load(row)

    if (
        not answered and not last_skip and state.get("asked")
        and is_steering_message(text) and not _SKIP.search(text)
    ):
        # "没听清", "能再说一遍吗": repeat the words said last, exactly; record nothing.
        return state.get("last_text") or None

    return await _next_step(
        db, scope, row, store, state, profile_id,
        just_introduced=just_introduced, skipped=last_skip,
    )


def _skip_prefix(skipped: bool) -> str:
    return f"{SKIP_TEXT}\n" if skipped else ""


async def _said(db: AsyncSession, row: Any, text: str, *, prefix: str) -> str:
    """What the candidate is shown, remembered as the last thing said (for "没听清")."""
    await _save(db, row, last_text=text)
    return prefix + text


async def _next_step(
    db: AsyncSession,
    scope: RunScope,
    row: Any,
    store: InterviewStore,
    state: dict[str, Any],
    profile_id: str,
    *,
    just_introduced: bool,
    skipped: bool,
) -> str | None:
    mock_session_id = row.id
    main_limit, followup_limit = guard.limits(row)
    must = await guard.must_have_of(scope, row)
    asked_candidates = []
    for entry in state.get("asked") or []:
        question = await store.get_question(entry["question_id"])
        if question is not None:
            asked_candidates.append(Candidate(
                question_id=question.id, stem=question_match_text(question.stem, question.tags),
            ))
    available = await _bank(store, profile_id, row.job_id)
    if not state.get("asked"):
        # Filled once, before the first question: the pool then covers the job's must-haves.
        available = await _fill_pool(db, store, row, profile_id, must, available)

    for _ in range(3):  # a judged-closed main question moves on to the next one at most twice
        state = _load(row)
        flow = _flow_state(row, state, main_limit, followup_limit)
        decision = decide(flow, must_have=must, available=available,
                          asked_candidates=asked_candidates)
        if decision.action is Action.JUDGE_FOLLOWUP:
            main = await store.get_question(decision.question_id)
            if main is None:
                return None
            attempt = await store.get_latest_attempt_in_session(main.id, mock_session_id)
            answer = attempt.user_answer if attempt else ""
            used = sum(1 for a in state["asked"]
                       if a["kind"] == "followup" and a.get("parent_question_id") == main.id)
            question = await _judge_followup(main.stem, answer, used)
            if question:
                result = await guard.ask(
                    scope, mock_session_id=mock_session_id, kind="followup",
                    stem=question, parent_question_id=main.id,
                )
                if result.get("accepted"):
                    return await _said(db, row, question, prefix=_skip_prefix(skipped))
            closed = list(state.get("closed_mains") or [])
            closed.append(main.id)
            await _save(db, row, closed_mains=closed)
            continue
        if decision.action is Action.ASK_MAIN:
            chosen = await store.get_question(decision.question_id)
            if chosen is None:
                return None
            result = await guard.ask(scope, mock_session_id=mock_session_id,
                                     question_id=chosen.id, kind="main")
            if not result.get("accepted"):
                logger.info("main question refused by the server: %s", result.get("code"))
                return None
            wording = await _phrase(chosen.stem)
            prefix = f"{AFTER_INTRO_TEXT}\n" if just_introduced else _skip_prefix(skipped)
            return await _said(db, row, wording, prefix=prefix)
        if decision.action is Action.OPEN_QA and not state.get("asked"):
            # Nothing could be asked at all (no bank question for this job and none could be
            # written). The interview ends here, rather than handing the floor to the candidate.
            await guard.end(scope, mock_session_id=mock_session_id, reason="user_ended")
            return NO_QUESTIONS_TEXT
        if decision.action is Action.OPEN_QA:
            result = await guard.open_qa(scope, mock_session_id=mock_session_id)
            if not result.get("accepted"):
                # The bank cannot yet support ending the questions (a must-have is uncovered).
                # The model asks one more question then; this turn is not decided here.
                return None
            return QA_OPEN_TEXT
        if decision.action is Action.CLOSE:
            return CLOSING_TEXT
        # The last question has no answer yet: the candidate's message was not an answer
        # (empty, or not recorded), so the question on the table is said again.
        if state.get("asked"):
            on_table = await store.get_question(state["asked"][-1]["question_id"])
            return on_table.stem if on_table else None
        return None
    return None

