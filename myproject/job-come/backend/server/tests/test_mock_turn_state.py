"""ADR-008 step 2: the transitions, one row each, and the scenarios S1–S5 at the level of state.

Pure. The text the interviewer says is checked by kind here; the wording is the caller's."""

from __future__ import annotations

import pytest

from jc.services.mock_turn_events import Event
from jc.services.mock_turn_state import Say, TurnState, apply, ask, open_qa, remember


def _kinds(result) -> list[str]:
    return [s.kind for s in result.says]


def _started() -> TurnState:
    """Opening sent, introduction done, nothing asked yet."""
    return apply(apply(TurnState(), Event.OPEN).state, Event.INTRO).state


def _with_main(qid="q1") -> TurnState:
    return ask(_started(), qid, kind="main")


# --- one row per case ---------------------------------------------------------------------------


def test_empty_changes_nothing():
    state = _with_main()
    assert apply(state, Event.EMPTY) == type(apply(state, Event.EMPTY))(state)


def test_the_first_message_asks_for_the_server_opening():
    result = apply(TurnState(), Event.OPEN)
    assert result.state.opening_sent and _kinds(result) == [Say.OPENING]
    assert result.advance is False


def test_the_introduction_is_acknowledged_and_the_next_question_is_chosen():
    result = apply(apply(TurnState(), Event.OPEN).state, Event.INTRO)
    assert result.state.intro_done
    assert _kinds(result) == [Say.INTRO_ACK]
    assert result.says[0].text.startswith("好，谢谢你的介绍")
    assert result.advance is True


def test_an_answer_puts_the_question_off_the_table_and_hands_on_to_decide():
    result = apply(_with_main(), Event.ANSWER)
    assert result.state.on_table is False
    assert result.advance is True and result.says == ()


def test_an_answer_with_nothing_on_the_table_is_not_recorded_and_moves_nothing():
    result = apply(_started(), Event.ANSWER)
    assert result.state == _started()
    assert result.advance is False


def test_talk_with_nothing_on_the_table_repeats_the_last_words_and_records_nothing():
    state = remember(_started(), "请讲一个你用 Python 做过的事。")
    result = apply(state, Event.TALK)
    assert result.state == state
    assert _kinds(result) == [Say.REPEAT]
    assert result.says[0].text == "请讲一个你用 Python 做过的事。"


def test_a_skip_closes_its_main_question_and_hands_on():
    result = apply(_with_main("q1"), Event.SKIP)
    assert "q1" in result.state.closed_mains
    assert result.state.on_table is False
    assert _kinds(result) == [Say.SKIP_ACK] and result.advance is True


def _followed_up(qid="q1", fid="f1") -> TurnState:
    """A main question answered, and a follow-up on it now on the table."""
    answered = apply(_with_main(qid), Event.ANSWER).state
    return ask(answered, fid, kind="followup", parent_id=qid)


def test_a_skip_of_a_follow_up_closes_its_main_question_too():
    state = _followed_up()
    result = apply(state, Event.SKIP)
    assert "q1" in result.state.closed_mains
    assert "f1" not in result.state.closed_mains


def test_a_skip_with_nothing_on_the_table_only_moves_on():
    result = apply(_started(), Event.SKIP)
    assert result.says == () and result.advance is True


def test_a_repeat_says_the_last_words_exactly_and_moves_nothing():
    state = remember(_with_main(), "请讲讲你的项目。")
    result = apply(state, Event.REPEAT)
    assert result.state == state
    assert result.says[0] == type(result.says[0])(Say.REPEAT, "请讲讲你的项目。")
    assert result.advance is False


def test_end_closes_the_interview_from_any_state():
    result = apply(_with_main(), Event.END)
    assert result.state.ended
    assert _kinds(result) == [Say.CLOSING]
    assert result.advance is False


def test_the_candidates_question_gets_the_answer_kind_and_changes_nothing():
    state = open_qa(_started()).state
    result = apply(state, Event.CANDIDATE_QUESTION)
    assert result.state == state
    assert _kinds(result) == [Say.CANDIDATE_ANSWER]


# --- guards -------------------------------------------------------------------------------------


def test_an_introduction_before_the_opening_is_refused():
    with pytest.raises(ValueError):
        apply(TurnState(), Event.INTRO)


def test_a_second_introduction_is_refused():
    with pytest.raises(ValueError):
        apply(_started(), Event.INTRO)


def test_a_question_cannot_be_put_while_one_is_on_the_table():
    with pytest.raises(ValueError):
        ask(_with_main("q1"), "q2", kind="main")


def test_a_follow_up_needs_its_main_question():
    with pytest.raises(ValueError):
        ask(_started(), "f1", kind="followup", parent_id=None)


def test_the_candidates_turn_cannot_open_with_a_question_on_the_table():
    with pytest.raises(ValueError):
        open_qa(_with_main())


# --- scenarios at the level of state ------------------------------------------------------------


def test_S4_repeat_after_the_introduction_says_the_question_again():
    state = remember(_with_main(), "讲讲你做过的一次性能优化。")
    result = apply(state, Event.REPEAT)
    assert result.says[0].text == "讲讲你做过的一次性能优化。"
    assert result.state.asked == state.asked  # nothing recorded


def test_S2_answer_then_skip_with_nothing_on_the_table_only_moves_on():
    """After an answer the table is clear; a skip then changes nothing and hands on to decide."""
    state = apply(_with_main("q1"), Event.ANSWER).state
    result = apply(state, Event.SKIP)
    assert result.advance is True
    assert result.state.closed_mains == frozenset()   # answered, not skipped: nothing closed
    assert _kinds(result) == []


def test_S3_skipping_a_follow_up_means_no_second_follow_up_on_its_main():
    state = _followed_up("q1", "f1")
    result = apply(state, Event.SKIP)
    assert "q1" in result.state.closed_mains
    # The main is closed, so decide will not judge a follow-up on it again.
    flow = result.state.flow(main_limit=5, followup_limit=2)
    assert "q1" in flow.closed_mains


def test_S5_end_after_an_answer_ends_without_another_question():
    state = apply(_with_main("q1"), Event.ANSWER).state
    result = apply(state, Event.END)
    assert result.state.ended and result.advance is False


def test_the_state_converts_to_the_flow_that_decide_reads():
    state = ask(_started(), "q1", kind="main")
    flow = state.flow(main_limit=5, followup_limit=2)
    assert flow.asked[0].question_id == "q1"
    assert flow.answered == 0 and flow.opening_sent and flow.intro_done
