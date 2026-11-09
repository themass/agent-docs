"""The server decides the interview's next step; the model's output is checked before use."""

from __future__ import annotations

import pytest

from jc.coach.coverage import Candidate
from jc.services.mock_flow import (
    Action,
    FlowState,
    Turn,
    check_followup,
    check_phrasing,
    decide,
)

AB = Candidate("q_ab", "如何设计一次A/B测试来验证转化提升？", None)
FUNNEL = Candidate("q_funnel", "请讲一个你用漏斗分析定位问题的例子。", None)


def _state(**overrides) -> FlowState:
    base = dict(
        opening_sent=True,
        intro_done=True,
        asked=(),
        answered=0,
        closed_mains=frozenset(),
        candidate_qa=False,
        ended=False,
        main_limit=5,
        followup_limit=2,
    )
    base.update(overrides)
    return FlowState(**base)


def _decide(state: FlowState, *, must=("A/B 测试",), available=(AB, FUNNEL), asked=()):
    return decide(
        state,
        must_have=list(must),
        available=list(available),
        asked_candidates=list(asked),
    )


# --- the flow -----------------------------------------------------------------------------------


def test_closed_interview_closes_whatever_else_is_pending():
    assert _decide(_state(ended=True, opening_sent=False)).action is Action.CLOSE


def test_opening_comes_first():
    assert _decide(_state(opening_sent=False)).action is Action.OPEN


def test_waits_for_the_self_introduction_before_any_question():
    decision = _decide(_state(intro_done=False))
    assert decision.action is Action.AWAIT_INTRO


def test_first_question_is_the_server_choice_for_the_first_uncovered_requirement():
    decision = _decide(_state())
    assert decision.action is Action.ASK_MAIN
    assert decision.question_id == "q_ab"


def test_unanswered_question_waits():
    state = _state(asked=(Turn("q_ab", "main"),), answered=0)
    assert _decide(state).action is Action.WAIT_ANSWER


def test_answered_main_is_followed_up_while_followups_remain():
    state = _state(asked=(Turn("q_ab", "main"),), answered=1)
    decision = _decide(state)
    assert decision.action is Action.JUDGE_FOLLOWUP
    assert decision.question_id == "q_ab"


def test_follow_up_limit_moves_on_to_the_next_main():
    asked = (
        Turn("q_ab", "main"),
        Turn("f1", "followup", "q_ab"),
        Turn("f2", "followup", "q_ab"),
    )
    decision = _decide(_state(asked=asked, answered=3, followup_limit=2), asked=[AB])
    assert decision.action is Action.ASK_MAIN
    assert decision.question_id == "q_funnel"


def test_judged_closed_main_is_not_followed_up_again():
    state = _state(
        asked=(Turn("q_ab", "main"),), answered=1, closed_mains=frozenset({"q_ab"}),
    )
    assert _decide(state, asked=[AB]).action is Action.ASK_MAIN


def test_main_limit_ends_with_candidate_questions():
    asked = (Turn("q_ab", "main"), Turn("q_funnel", "main"))
    state = _state(asked=asked, answered=2, closed_mains=frozenset({"q_ab", "q_funnel"}),
                   main_limit=2)
    assert _decide(state).action is Action.OPEN_QA


def test_no_question_left_to_ask_goes_to_candidate_questions_not_a_made_up_one():
    decision = _decide(_state(), available=())
    assert decision.action is Action.OPEN_QA


def test_candidate_question_turn_stays_open_until_the_interview_ends():
    assert _decide(_state(candidate_qa=True)).action is Action.OPEN_QA
    assert _decide(_state(candidate_qa=True, ended=True)).action is Action.CLOSE


def test_decision_is_a_pure_function_of_the_state():
    state = _state(asked=(Turn("q_ab", "main"),), answered=1)
    assert _decide(state) == _decide(state)


# --- the follow-up judgement --------------------------------------------------------------------

ANSWER = "我们用了两周做A/B测试，样本量按照每组五千人来定，最后转化提升了百分之三。"


def test_no_follow_up_is_always_acceptable():
    assert check_followup({"followup": False}, ANSWER).ok


def test_follow_up_quoting_the_answer_is_accepted():
    result = {"followup": True, "question": "五千人这个样本量是怎么算出来的？",
              "quotes": ["样本量按照每组五千人来定"]}
    assert check_followup(result, ANSWER).ok


@pytest.mark.parametrize(
    "result, reason",
    [
        ({"followup": True, "question": "", "quotes": ["两周"]}, "empty_question"),
        ({"followup": True, "question": "为什么？那怎么做？", "quotes": ["两周"]},
         "not_one_question"),
        ({"followup": True, "question": "你刚说样本量是多少？", "quotes": ["两周"]},
         "refers_to_earlier_talk"),
        ({"followup": True, "question": "样本量怎么定的？", "quotes": []}, "no_quote"),
        ({"followup": True, "question": "样本量怎么定的？", "quotes": ["我们做过很多实验"]},
         "quote_not_in_answer"),
    ],
)
def test_bad_follow_up_is_refused_with_its_reason(result, reason):
    check = check_followup(result, ANSWER)
    assert not check.ok
    assert check.reason == reason


def test_quote_ignores_whitespace_differences():
    result = {"followup": True, "question": "样本量怎么定的？", "quotes": ["每组 五千人"]}
    assert check_followup(result, ANSWER).ok


# --- the wording of a main question -------------------------------------------------------------


def test_rewording_that_keeps_the_topic_is_accepted():
    assert check_phrasing(AB.stem, "你之前做过A/B测试吗，是怎么验证转化提升的？").ok


def test_wording_about_another_topic_is_refused():
    check = check_phrasing(AB.stem, "请讲讲你主导过的一个项目，最后做了什么取舍？")
    assert not check.ok and check.reason == "different_topic"


def test_wording_with_two_questions_is_refused():
    check = check_phrasing(AB.stem, "A/B测试怎么做？结果怎么样？")
    assert not check.ok and check.reason == "not_one_question"


def test_wording_that_points_back_is_refused():
    check = check_phrasing(AB.stem, "你刚说的A/B测试是怎么做的？")
    assert not check.ok and check.reason == "refers_to_earlier_talk"


def test_empty_or_long_wording_is_refused():
    assert check_phrasing(AB.stem, "  ").reason == "empty"
    assert check_phrasing(AB.stem, "A/B测试" * 60 + "？").reason == "too_long"
