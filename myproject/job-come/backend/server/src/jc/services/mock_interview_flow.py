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
from dataclasses import replace
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
from jc.services.mock_flow import (
    Action,
    Turn,
    check_followup,
    check_phrasing,
    decide,
)
from jc.services.mock_opening import opening_text
from jc.services.mock_turn_events import Event, Flags, resolve, utterance
from jc.services.mock_turn_state import TurnState, apply, ask, open_qa, remember
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


async def _save(db: AsyncSession, row: Any, **updates: Any) -> None:
    # Read the stored value again: the guards commit their own changes to the same row.
    current = dict(row.coverage or {})
    current.update(updates)
    row.coverage = current
    await db.flush()
    await db.commit()


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


#: Angles a second and third question on the same requirement take, so one requirement can carry
#: more than one question (an interview may have more main questions than requirements).
STEM_ANGLES = (
    "",
    "一次取舍或决策：你当时怎么判断，依据是什么",
    "一次出错或复盘：出了什么问题，怎么处理的",
)


async def _stem_for(
    requirement: str, job_title: str | None, job_text: str | None, angle: str = "",
) -> str | None:
    """A main question for one must-have, written by the model and checked. None when it fails."""
    data = await _model_json(
        MOCK_FLOW_SKILL,
        {"task": "stem", "requirement": requirement, "angle": angle,
         "job_title": job_title or "", "job_text": (job_text or "")[:1500]},
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
    pool: list[Candidate], target: int,
) -> list[Candidate]:
    """Writes main questions into the job's bank (source mock, tagged with the requirement) until
    the bank carries `target` questions. Every requirement the bank does not cover gets one first;
    then more, on other angles, round by round. The next session finds them in the bank."""
    if not row.job_id or not must or len(pool) >= target:
        return pool
    job = await db.get(Job, row.job_id)
    title = job.title if job else None
    text = job.raw_text if job else None
    covered = coverage_of(must, [c.stem for c in pool]).covered
    added = list(pool)

    async def write(requirement: str, angle: str) -> None:
        stem = await _stem_for(requirement, title, text, angle)
        if stem is None:
            return
        question = InterviewQuestion(
            id=new_id("iq"), profile_id=profile_id, job_id=row.job_id, stem=stem,
            question_type="behavioral", source=QuestionSource.MOCK, tags=[requirement],
        )
        await store.create_question(question)
        added.append(Candidate(question_id=question.id,
                               stem=question_match_text(stem, [requirement])))

    for requirement in must:
        if requirement not in covered:
            await write(requirement, STEM_ANGLES[0])
    for angle in STEM_ANGLES[1:]:
        for requirement in must:
            if len(added) >= target:
                break
            await write(requirement, angle)
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


def _turn_state(row: Any) -> TurnState:
    """The interview's state, read from the session. The guards own `asked`; the flow the rest."""
    c = dict(row.coverage or {})
    asked = tuple(
        Turn(a["question_id"], a["kind"], a.get("parent_question_id"))
        for a in c.get("asked") or []
    )
    return TurnState(
        opening_sent=bool(c.get("opening_sent")),
        intro_done=bool(c.get("intro_done")),
        asked=asked,
        answered=min(int(c.get("answered_upto") or 0), len(asked)),
        closed_mains=frozenset(c.get("closed_mains") or []),
        candidate_qa=bool(c.get("candidate_qa")),
        ended=row.status != MockSessionStatus.ACTIVE,
        last_said=c.get("last_text") or None,
    )


async def _persist(db: AsyncSession, row: Any, ts: TurnState, **extra: Any) -> None:
    """The flow's own fields, written once per turn. `asked` is written by the guards, not here."""
    await _save(
        db, row,
        opening_sent=ts.opening_sent,
        intro_done=ts.intro_done,
        answered_upto=ts.answered,
        closed_mains=sorted(ts.closed_mains),
        last_text=ts.last_said,
        **extra,
    )


def _flags(ts: TurnState) -> Flags:
    return Flags(
        opening_sent=ts.opening_sent,
        intro_done=ts.intro_done,
        on_table=ts.on_table,
        candidate_qa=ts.candidate_qa,
        ended=ts.ended,
    )


async def run_turn(
    db: AsyncSession,
    *,
    user_id: str,
    profile_id: str,
    mock_session_id: str,
    text: str,
    answered: bool,
) -> str | None:
    """The reply to one candidate message in a mock interview (ADR-008).

    The message is classified (`resolve`), the transition is `apply`, and when the flow must choose
    a next step, `decide` does. The reply is built from what `apply` says. `answered` is whether
    `record_mock_answer` recorded the message as an answer; the state decides, not this flag."""
    store = InterviewStore(db)
    row = await store.get_mock_session(mock_session_id)
    if row is None or row.profile_id != profile_id:
        return None
    scope = RunScope(db=db, user_id=user_id, profile_id=profile_id, mock_session_id=mock_session_id)
    ts = _turn_state(row)
    event = resolve(utterance(text), _flags(ts))

    if event is Event.CANDIDATE_QUESTION:
        # Their turn to ask: the words are answered from the job text. Nothing in the flow changes.
        return await _answer_candidate(db, row, text)

    if event is Event.EMPTY:
        return ""

    if event is Event.END:
        reason = "completed" if ts.candidate_qa else "user_ended"
        await guard.end(scope, mock_session_id=mock_session_id, reason=reason)
        ts = apply(ts, Event.END).state
        await _persist(db, row, ts)
        return CLOSING_TEXT

    if event is Event.REPEAT:
        # "没听清": the words said last, exactly. Nothing is recorded or moved.
        return ts.last_said or ""

    if event is Event.OPEN:
        job = await db.get(Job, row.job_id) if row.job_id else None
        opening = opening_text(job.company if job else None, job.title if job else None)
        ts = apply(ts, Event.OPEN).state
        ts = remember(ts, opening)
        await _persist(db, row, ts, opening_text=opening)
        return opening

    if event is Event.SKIP and ts.on_table:
        await guard.skip(
            scope, mock_session_id=mock_session_id, question_id=ts.asked[-1].question_id,
        )

    # Every other event: the transition, then the next step if the flow must choose one.
    result = apply(ts, event)
    ts = result.state
    fixed = [said.text for said in result.says if said.text]
    question: str | None = None
    if result.advance:
        question, ts = await _choose_next(db, scope, row, store, ts, profile_id)
        fixed.append(question)
    reply = "\n".join(fixed)
    if not reply:
        await _persist(db, row, ts)
        return ""
    # "没听清" repeats the question, not the acknowledgement before it.
    ts = remember(ts, question if result.advance and question else reply)
    await _persist(db, row, ts)
    return reply


async def _choose_next(
    db: AsyncSession,
    scope: RunScope,
    row: Any,
    store: InterviewStore,
    ts: TurnState,
    profile_id: str,
) -> tuple[str | None, TurnState]:
    """`decide` on the state, and the server's action for it. Returns the text to show next (None
    when the flow has nothing to say yet) and the state after it."""
    mock_session_id = row.id
    main_limit, followup_limit = guard.limits(row)
    must = await guard.must_have_of(scope, row)
    asked_candidates = []
    for turn in ts.asked:
        question = await store.get_question(turn.question_id)
        if question is not None:
            asked_candidates.append(Candidate(
                question_id=question.id, stem=question_match_text(question.stem, question.tags),
            ))
    available = await _bank(store, profile_id, row.job_id)
    if not ts.asked:
        # Filled once, before the first question: the bank then carries every main question the
        # interview can ask, so a refused or skipped question never empties it.
        available = await _fill_pool(db, store, row, profile_id, must, available, main_limit + 1)

    refused: set[str] = set()
    for _ in range(3 + len(available)):  # a judged-closed or refused question moves on to the next
        pool = [c for c in available if c.question_id not in refused]
        decision = decide(
            ts.flow(main_limit=main_limit, followup_limit=followup_limit),
            must_have=must, available=pool, asked_candidates=asked_candidates,
        )
        if decision.action is Action.JUDGE_FOLLOWUP:
            main = await store.get_question(decision.question_id)
            if main is None:
                ts = replace(ts, closed_mains=ts.closed_mains | {decision.question_id})
                continue
            attempt = await store.get_latest_attempt_in_session(main.id, mock_session_id)
            answer = attempt.user_answer if attempt else ""
            used = sum(1 for t in ts.asked
                       if t.kind == "followup" and t.parent_question_id == main.id)
            question = await _judge_followup(main.stem, answer, used)
            if question:
                result = await guard.ask(
                    scope, mock_session_id=mock_session_id, kind="followup",
                    stem=question, parent_question_id=main.id,
                )
                if result.get("accepted"):
                    ts = ask(ts, result["question_id"], kind="followup", parent_id=main.id)
                    return question, ts
            # The judge found nothing to follow up: this main is done, the next one comes.
            ts = replace(ts, closed_mains=ts.closed_mains | {main.id})
            continue
        if decision.action is Action.ASK_MAIN:
            chosen = await store.get_question(decision.question_id)
            if chosen is None:
                refused.add(decision.question_id)
                continue
            result = await guard.ask(scope, mock_session_id=mock_session_id,
                                     question_id=chosen.id, kind="main")
            if not result.get("accepted"):
                # The guard refused this question (already asked, or too like one asked). Another
                # question is offered instead: the candidate is never handed to the model for it.
                logger.warning("main question %s refused by the guard: %s",
                               chosen.id, result.get("code"))
                refused.add(chosen.id)
                continue
            ts = ask(ts, chosen.id, kind="main")
            return await _phrase(chosen.stem), ts
        if decision.action is Action.OPEN_QA and not ts.asked:
            # Nothing could be asked at all: the interview ends here, not on the candidate's turn.
            await guard.end(scope, mock_session_id=mock_session_id, reason="user_ended")
            return NO_QUESTIONS_TEXT, apply(ts, Event.END).state
        if decision.action is Action.OPEN_QA:
            result = await guard.open_qa(scope, mock_session_id=mock_session_id)
            if not result.get("accepted"):
                # The guard will not open the candidate's turn yet (a must-have is uncovered and
                # the questions are not all asked). The bank cannot cover it: the interview ends.
                logger.warning("interview %s: candidate turn refused: %s", row.id,
                               result.get("code"))
                await guard.end(scope, mock_session_id=row.id, reason="user_ended")
                return NO_QUESTIONS_TEXT, apply(ts, Event.END).state
            return QA_OPEN_TEXT, open_qa(ts).state
        if decision.action is Action.CLOSE:
            return CLOSING_TEXT, apply(ts, Event.END).state
        # Nothing for the flow to say next: an interview that cannot go on ends, rather than being
        # handed to the model (ADR-008). The reason is in the log.
        logger.warning("interview %s has no next step (%s): ending it", row.id, decision.action)
        await guard.end(scope, mock_session_id=row.id, reason="user_ended")
        return NO_QUESTIONS_TEXT, apply(ts, Event.END).state
    logger.warning("interview %s: no question could be offered: ending it", row.id)
    await guard.end(scope, mock_session_id=row.id, reason="user_ended")
    return NO_QUESTIONS_TEXT, apply(ts, Event.END).state
