"""What the candidate's message means in a mock interview (ADR-008, step 1).

Pure: no database, no model.

Two steps, each with one job:

1. `utterance(text)` says what the words are, with no regard to the interview: a command to end, to
   skip, to repeat, or ordinary words. There is one place for the command words.
2. `resolve(utterance, state)` says what the message is in this interview: the self-introduction,
   an answer, a skip, a repeat, the candidate's own question, or nothing. The state decides.

The table in `resolve` is the rule. Everything else in the interview asks it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from jc.services.mock_answer_recorder import is_refusal, is_steering_message

_END = re.compile(r"结束|终止|停止")
_SKIP = re.compile(r"下一|换一|换个|跳过")
_REPEAT = re.compile(r"没听|再说一遍|重复|再问一遍|重新说|再讲一遍")
_NOTHING = re.compile(r"[\s。，、！？!?,.;；：:~…\-—？]+")


class Utterance(StrEnum):
    EMPTY = "empty"      # nothing but spaces, punctuation or a bare filler
    END = "end"          # "结束", "我想结束这场面试"
    SKIP = "skip"        # "下一题", "换一题", "跳过"
    REFUSE = "refuse"    # "这题我不想答", "不回答" (the whole message; not an answer, not scored)
    REPEAT = "repeat"    # "没听清", "能再说一遍吗"
    WORDS = "words"      # anything else: the candidate speaking to the question


class Event(StrEnum):
    EMPTY = "empty"
    OPEN = "open"                          # the first message: the server writes the opening
    INTRO = "intro"                        # the self-introduction, after the opening
    ANSWER = "answer"                      # words about the question on the table
    TALK = "talk"                          # ordinary words with no question on the table
    SKIP = "skip"
    REPEAT = "repeat"
    END = "end"
    CANDIDATE_QUESTION = "candidate_question"  # the candidate's turn to ask questions


@dataclass(frozen=True)
class Flags:
    """The part of the interview state that decides what a message is. Nothing else."""

    opening_sent: bool
    intro_done: bool
    #: A question is on the table: it was asked, and the candidate has not moved past it.
    on_table: bool
    candidate_qa: bool
    ended: bool


def utterance(text: str) -> Utterance:
    """What the words are. The command words are matched here and nowhere else."""
    if not _NOTHING.sub("", text or ""):
        return Utterance.EMPTY
    if is_refusal(text):
        return Utterance.REFUSE
    if not is_steering_message(text):
        return Utterance.WORDS
    if _END.search(text):
        return Utterance.END
    if _SKIP.search(text):
        return Utterance.SKIP
    if _REPEAT.search(text):
        return Utterance.REPEAT
    return Utterance.WORDS


def resolve(said: Utterance, flags: Flags) -> Event:
    """What the message is in this interview. The rule table: one row per case in ADR-008 §3.

    A command word is the same event whether or not a question is on the table: `apply` decides
    what a skip or a repeat changes when there is nothing to skip or repeat."""
    if said is Utterance.EMPTY:
        return Event.EMPTY
    if flags.ended or said is Utterance.END:
        return Event.END
    if flags.candidate_qa:
        # The candidate's turn: words are a question to the interviewer. A command word is not an
        # answer to anything, so it closes the interview (ADR-008 S9).
        return Event.CANDIDATE_QUESTION if said is Utterance.WORDS else Event.END
    if not flags.opening_sent:
        return Event.OPEN
    if not flags.intro_done:
        return Event.INTRO
    if said is Utterance.SKIP:
        return Event.SKIP
    if said is Utterance.REFUSE:
        # A refusal moves on from the question like a skip, and the question is not scored.
        return Event.SKIP if flags.on_table else Event.TALK
    if said is Utterance.REPEAT:
        return Event.REPEAT
    # Ordinary words. With a question on the table they answer it; with none (nothing asked yet,
    # or the question was just skipped) they are talk, and are not recorded as an answer.
    return Event.ANSWER if flags.on_table else Event.TALK
