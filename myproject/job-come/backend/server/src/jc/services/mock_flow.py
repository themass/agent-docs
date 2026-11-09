"""The mock interview's flow, decided by the server. Pure: no database and no model.

The server decides what happens next from the recorded state (`decide`). The model is asked only
for two things, each checked before it is used: whether the last answer needs one follow-up
(`check_followup`), and how to word a chosen main question (`check_phrasing`). Everything the
candidate sees is then written from this state, so the ledger and the candidate's messages agree.

Limits (main questions, follow-ups per main question) are passed in, so this module does not depend
on the session's quota rules.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from jc.coach.coverage import Candidate, key_terms, pick_next
from jc.services.interview_reply import question_count, refers_to_earlier_talk

#: A wording longer than this is not a question the candidate can answer in one go.
MAX_QUESTION_CHARS = 200

_SPACES = re.compile(r"\s+")


class Action(StrEnum):
    OPEN = "open"                        # the server writes the opening
    AWAIT_INTRO = "await_intro"          # waiting for the self-introduction
    WAIT_ANSWER = "wait_answer"          # the last question has no answer yet
    JUDGE_FOLLOWUP = "judge_followup"    # ask the model whether the last answer needs a follow-up
    ASK_MAIN = "ask_main"                # ask the main question chosen by the server
    OPEN_QA = "open_qa"                  # candidate's turn to ask questions
    CLOSE = "close"                      # the server writes the closing line


@dataclass(frozen=True)
class Turn:
    """A question already asked in this interview, in order."""

    question_id: str
    kind: str  # "main" | "followup"
    parent_question_id: str | None = None


@dataclass(frozen=True)
class FlowState:
    opening_sent: bool
    intro_done: bool
    asked: tuple[Turn, ...]
    #: How many of `asked` have a candidate answer recorded. Answers come in order.
    answered: int
    #: Main questions whose follow-up judge already said "no more".
    closed_mains: frozenset[str]
    candidate_qa: bool
    ended: bool
    main_limit: int
    followup_limit: int


@dataclass(frozen=True)
class Decision:
    action: Action
    #: For ASK_MAIN: the question to ask. For JUDGE_FOLLOWUP: the main question being followed up.
    question_id: str | None = None


def _followups_of(asked: Sequence[Turn], main_id: str) -> int:
    return sum(1 for t in asked if t.kind == "followup" and t.parent_question_id == main_id)


def decide(
    state: FlowState,
    *,
    must_have: Sequence[str],
    available: Sequence[Candidate],
    asked_candidates: Sequence[Candidate],
) -> Decision:
    """The next step for this interview. Pure: the same state always gives the same decision."""
    if state.ended:
        return Decision(Action.CLOSE)
    if not state.opening_sent:
        return Decision(Action.OPEN)
    if not state.intro_done:
        return Decision(Action.AWAIT_INTRO)
    if state.candidate_qa:
        return Decision(Action.OPEN_QA)
    if state.asked and state.answered < len(state.asked):
        return Decision(Action.WAIT_ANSWER)
    mains = [t for t in state.asked if t.kind == "main"]
    if mains:
        last_main = mains[-1].question_id
        if (
            state.asked
            and last_main not in state.closed_mains
            and _followups_of(state.asked, last_main) < state.followup_limit
        ):
            return Decision(Action.JUDGE_FOLLOWUP, last_main)
    if len(mains) >= state.main_limit:
        return Decision(Action.OPEN_QA)
    chosen = pick_next(must_have, asked_candidates, available)
    if chosen is None:
        # Every requirement is covered. The interview still runs to its main-question limit, on the
        # bank's questions in their given order, rather than ending early.
        asked_ids = {c.question_id for c in asked_candidates}
        chosen = next((c for c in available if c.question_id not in asked_ids), None)
    if chosen is None:
        return Decision(Action.OPEN_QA)
    return Decision(Action.ASK_MAIN, chosen.question_id)


@dataclass(frozen=True)
class Check:
    ok: bool
    reason: str = ""


def _squash(text: str) -> str:
    return _SPACES.sub("", text or "")


def check_followup(result: dict, answer: str) -> Check:
    """The model's follow-up judgement, before it is used.

    A follow-up must be one question, must not point back at an earlier answer, and must quote the
    candidate's own words (each quote a substring of the answer, so it cannot be invented).
    """
    if not result.get("followup"):
        return Check(True)
    question = (result.get("question") or "").strip()
    if not question:
        return Check(False, "empty_question")
    if question_count(question) != 1:
        return Check(False, "not_one_question")
    if refers_to_earlier_talk(question):
        return Check(False, "refers_to_earlier_talk")
    quotes = [q for q in (result.get("quotes") or []) if isinstance(q, str) and q.strip()]
    if not quotes:
        return Check(False, "no_quote")
    answer_text = _squash(answer)
    if any(_squash(q) not in answer_text for q in quotes):
        return Check(False, "quote_not_in_answer")
    return Check(True)


def check_phrasing(stem: str, phrased: str) -> Check:
    """The model's wording of a chosen main question, before it is shown.

    One question, not pointing back, not too long, and sharing at least one key term with the stem.
    The last check is weak: Chinese key terms are character pairs, and a fair rewording shares only
    a few. It catches a wording about a different topic, not a subtle drift. The ledger records the
    bank question's id, so the topic stays the bank's.
    """
    text = (phrased or "").strip()
    if not text:
        return Check(False, "empty")
    if len(text) > MAX_QUESTION_CHARS:
        return Check(False, "too_long")
    if question_count(text) != 1:
        return Check(False, "not_one_question")
    if refers_to_earlier_talk(text):
        return Check(False, "refers_to_earlier_talk")
    if key_terms(stem) and not (key_terms(stem) & key_terms(text)):
        return Check(False, "different_topic")
    return Check(True)
