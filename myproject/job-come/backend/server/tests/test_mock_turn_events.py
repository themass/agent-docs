"""ADR-008 step 1: every message is classified, and the rule table decides what it is.

These are pure tests. They do not touch the database or a model."""

from __future__ import annotations

import itertools

import pytest

from jc.services.mock_turn_events import Event, Flags, Utterance, resolve, utterance


def _flags(**overrides) -> Flags:
    base = dict(opening_sent=True, intro_done=True, on_table=True, candidate_qa=False, ended=False)
    base.update(overrides)
    return Flags(**base)


# --- what the words are -------------------------------------------------------------------------


@pytest.mark.parametrize("text, said", [
    ("", Utterance.EMPTY),
    ("   ", Utterance.EMPTY),
    ("。？！", Utterance.EMPTY),
    ("下一题", Utterance.SKIP),
    ("好的，下一题", Utterance.SKIP),
    ("换一题吧", Utterance.SKIP),
    ("跳过", Utterance.SKIP),
    ("没听清，能再说一遍吗", Utterance.REPEAT),
    ("请再说一遍", Utterance.REPEAT),
    ("结束", Utterance.END),
    ("我想结束这场面试", Utterance.END),
    ("我做过三年用户增长", Utterance.WORDS),
    ("这题我不想答", Utterance.REFUSE),
    ("我不想回答这个问题。", Utterance.REFUSE),
    ("不回答", Utterance.REFUSE),
    ("我不想回答这种问题，因为我们从没碰过", Utterance.WORDS),
    ("我不想跳槽", Utterance.WORDS),
    ("好的", Utterance.WORDS),
    ("我们把结算拆成两张表，耗时三周。", Utterance.WORDS),
])
def test_words_are_classified(text, said):
    assert utterance(text) is said


def test_a_sentence_that_mentions_a_command_word_is_an_answer():
    # "跳过" inside a real answer is talk about the work, not a command. The closed list decides.
    assert utterance("我们在上线前跳过了压测，后来出过事故") is Utterance.WORDS
    assert utterance("我负责结算的结束状态机设计") is Utterance.WORDS


# --- what the message is in this interview ------------------------------------------------------


def test_nothing_but_filler_is_empty_whatever_the_state():
    for said, flags in itertools.product([Utterance.EMPTY], _all_flags()):
        assert resolve(said, flags) is Event.EMPTY


def test_end_closes_from_any_state():
    for flags in _all_flags():
        assert resolve(Utterance.END, flags) is Event.END


def test_once_ended_everything_is_end():
    for said, flags in _pairs(ended=True):
        if said is Utterance.EMPTY:
            continue
        assert resolve(said, flags) is Event.END


def test_the_first_message_opens_the_interview():
    flags = _flags(opening_sent=False, intro_done=False, on_table=False)
    assert resolve(Utterance.WORDS, flags) is Event.OPEN


def test_the_message_after_the_opening_is_the_introduction():
    flags = _flags(intro_done=False, on_table=False)
    assert resolve(Utterance.WORDS, flags) is Event.INTRO
    # Even a skip word there is the introduction: nothing is on the table to skip.
    assert resolve(Utterance.SKIP, flags) is Event.INTRO


def test_words_with_a_question_on_the_table_answer_it():
    assert resolve(Utterance.WORDS, _flags(on_table=True)) is Event.ANSWER


def test_words_with_no_question_on_the_table_are_talk_not_an_answer():
    assert resolve(Utterance.WORDS, _flags(on_table=False)) is Event.TALK


def test_skip_is_a_skip_when_a_question_is_on_the_table():
    assert resolve(Utterance.SKIP, _flags(on_table=True)) is Event.SKIP


def test_skip_with_nothing_on_the_table_is_still_a_skip_for_the_state_to_handle():
    assert resolve(Utterance.SKIP, _flags(on_table=False)) is Event.SKIP


def test_repeat_is_a_repeat_when_a_question_is_on_the_table():
    assert resolve(Utterance.REPEAT, _flags(on_table=True)) is Event.REPEAT


def test_a_refusal_with_a_question_on_the_table_is_a_skip_not_an_answer():
    assert resolve(Utterance.REFUSE, _flags(on_table=True)) is Event.SKIP


def test_a_refusal_with_nothing_on_the_table_is_talk():
    assert resolve(Utterance.REFUSE, _flags(on_table=False)) is Event.TALK


def test_in_the_candidates_turn_words_are_a_question_and_a_command_closes():
    flags = _flags(candidate_qa=True, on_table=False)
    assert resolve(Utterance.WORDS, flags) is Event.CANDIDATE_QUESTION
    assert resolve(Utterance.SKIP, flags) is Event.END   # ADR-008 S9
    assert resolve(Utterance.REPEAT, flags) is Event.END


# --- the whole table, exhaustively --------------------------------------------------------------


def _all_flags():
    for opening, intro, table, qa, ended in itertools.product([True, False], repeat=5):
        yield Flags(opening_sent=opening, intro_done=intro, on_table=table, candidate_qa=qa,
                    ended=ended)


def _pairs(**fixed):
    for said in Utterance:
        for flags in _all_flags():
            if all(getattr(flags, k) == v for k, v in fixed.items()):
                yield said, flags


def test_every_combination_has_exactly_one_event():
    """No input in any state is left without an event, and each resolves to a known Event."""
    count = 0
    for said in Utterance:
        for flags in _all_flags():
            event = resolve(said, flags)
            assert isinstance(event, Event)
            count += 1
    assert count == len(Utterance) * 32
