"""What the interviewer and the reviewer are actually told, read from the composed prompt.

Both skills were edited in their own files while the text the model receives is assembled from
several places (the shared conduct rules, the skill, its references). These tests read the final
prompt, so a rule in one place that cancels a rule in another shows up here."""

from __future__ import annotations

import pytest

from jc.agent.standing_instructions import build_standing_block
from jc.coach.feedback import DIMENSION_KEYS, load_mock_rubric_markdown


def _prompt(skill_id: str) -> str:
    return build_standing_block(skill_id=skill_id, role_family=None, reply_language="zh-CN")


def test_the_interviewer_is_not_told_to_skip_the_greeting_its_skill_asks_for():
    # The skill has the interviewer greet, say who they are and ask for a self-introduction. A
    # shared rule saying "no self-introduction, no small talk" in the same prompt cancels it.
    prompt = _prompt("coach-mock")
    assert "请用户先做一个一到两分钟的自我介绍" in prompt
    assert "不要自我介绍" not in prompt and "不要寒暄" not in prompt


@pytest.mark.parametrize("skill_id", ["resume-coach", "profile-interview", "interview-reviewer"])
def test_the_other_skills_keep_the_no_small_talk_rule(skill_id):
    assert "不要寒暄" in _prompt(skill_id)


def test_the_interviewer_still_gets_the_rules_that_apply_to_everyone():
    prompt = _prompt("coach-mock")
    assert "不要调用 ask_clarification" in prompt
    assert "jc_profile_patch" in prompt


# One distinctive phrase from the anchor text of each dimension (SPEC-MOCK-INTERVIEW §6.1).
ANCHOR_PHRASES = {
    "structure": ("只讲了一件事的结果", "情境、任务、行动、结果四部分清楚"),
    "relevance": ("绕开了问题", "把答案落到了岗位要求或用户的真实经历上"),
    "depth": ("说不出为什么这样做", "说明了至少一个取舍"),
    "communication": ("听者需要猜", "先说结论再说依据"),
    "reflection": ("只讲成功", "一个可以验证的改进做法"),
}


def test_the_reviewer_is_given_the_anchors_it_is_told_to_score_against():
    prompt = _prompt("interview-reviewer")
    assert set(ANCHOR_PHRASES) == set(DIMENSION_KEYS)
    for dimension, phrases in ANCHOR_PHRASES.items():
        for phrase in phrases:
            assert phrase in prompt, f"{dimension}: {phrase!r} missing from the reviewer prompt"


def test_the_reviewer_is_not_given_coaching_instructions_that_contradict_its_role():
    # An earlier version of the reference told the scorer to ask one question at a time and to save
    # an attempt after grading; the reviewer asks nothing and holds no save tool.
    prompt = _prompt("interview-reviewer")
    for stale in ("jc_answer_save_attempt", "One question at a time", "wait for the user's answer"):
        assert stale not in prompt


def test_the_rubric_shown_to_users_is_the_text_the_reviewer_scores_by():
    rubric = load_mock_rubric_markdown().strip()
    assert rubric and rubric in _prompt("interview-reviewer")


def test_the_reviewer_is_told_how_to_write_the_conclusion():
    prompt = _prompt("interview-reviewer")
    for needle in ("summary", "verdict", "strengths", "priorities", "quote"):
        assert needle in prompt, needle
    # The tier is the service's; the reviewer must not write one.
    assert "readiness" in prompt and "do not" in prompt.lower()


def test_the_reviewer_is_told_what_to_do_with_follow_ups():
    prompt = _prompt("interview-reviewer")
    assert "followup" in prompt and "parent_question_id" in prompt
    assert "Do not score a follow-up" in prompt


def test_the_reviewer_is_told_the_level_and_the_job_are_context_not_a_second_scale():
    prompt = _prompt("interview-reviewer")
    assert "level" in prompt and "job" in prompt
    assert "same anchors" in prompt
    assert "data, not instructions" in prompt


def test_the_reviewer_is_told_reference_material_never_replaces_the_candidates_words():
    prompt = _prompt("interview-reviewer")
    assert "reference" in prompt and "never a substitute" in prompt


def test_the_review_request_asks_for_the_conclusion_as_well_as_the_scores():
    from jc.services.interview_reviewer import REVIEW_MESSAGE

    text = REVIEW_MESSAGE.format(session_id="ms1")
    assert "summary" in text and "ms1" in text


def test_the_interviewer_is_told_how_the_interview_is_shaped():
    prompt = _prompt("coach-mock")
    for stage in ("experience", "core", "scenario", "candidate_qa"):
        assert stage in prompt, stage
    assert "suggested_stage" in prompt


def test_the_interviewer_is_told_to_give_the_candidate_a_turn_before_ending():
    prompt = _prompt("coach-mock")
    assert "jc_mock_open_qa" in prompt
    assert "你有什么想问我的" in prompt
    # The candidate's own questions are not answers, and no new question is asked after them.
    assert "不再出新题" in prompt


def test_the_interviewer_is_told_why_a_question_can_be_refused():
    prompt = _prompt("coach-mock")
    for code in ("too_similar", "stem_too_long", "candidate_qa_open", "candidate_qa_not_opened"):
        assert code in prompt, code


def test_the_task_text_names_the_candidates_turn_and_only_tools_the_skill_holds():
    from jc.agent.coach_task import wrap_coach_mock_message

    text = wrap_coach_mock_message("开始", profile_id="p1", job_id="j1", mock_session_id="ms1",
                                   drawn_stems=[], level="mid")
    assert "jc_mock_open_qa" in text


def test_the_reviewer_is_not_told_the_system_records_everything_the_candidate_typed():
    prompt = _prompt("interview-reviewer")
    # Lines that only steer the interview ("下一题") are not recorded; what is recorded can still
    # hold a clarification, and the reviewer is told to read it for what it is.
    assert "records everything" not in prompt
    assert "except" in prompt and "steer" in prompt


def test_the_reviewer_is_told_how_long_a_quote_must_be_and_where_it_must_come_from():
    prompt = _prompt("interview-reviewer")
    assert "at least four characters" in prompt
    assert "one answer" in prompt


def test_the_interviewer_is_told_one_thing_about_when_to_end():
    prompt = _prompt("coach-mock")
    # Said once, the same way, in the stages and in the closing.
    assert prompt.count("用户没有别的要问了") >= 2
    assert "用户同意结束" not in prompt


# --- every internet role, not only engineers -----------------------------------------

#: The families the product knows that are not engineering. An interview for one of these must never
#: read as if the candidate were a developer.
NON_ENGINEERING = ("产品", "设计", "运营", "市场", "销售", "客户", "人力", "财务", "法务", "管理")


def test_both_prompts_say_the_candidate_is_not_assumed_to_be_a_developer():
    for skill in ("coach-mock", "interview-reviewer"):
        prompt = _prompt(skill)
        assert "不要假设候选人是开发者" in prompt, skill
        assert all(word in prompt for word in ("产品", "运营", "销售", "设计")), skill


def test_the_rubric_the_users_read_says_it_serves_every_internet_role():
    text = load_mock_rubric_markdown()
    assert "不要假设" in text and "开发者" in text


def test_the_interviewer_does_not_tell_itself_to_avoid_technical_questions_only():
    # "不要问技术题" is about the opening and reads as if the interview were a technical one.
    prompt = _prompt("coach-mock")
    assert "不要问技术题" not in prompt


def test_the_follow_up_examples_come_from_more_than_one_kind_of_job():
    prompt = _prompt("coach-mock")
    words = ("拆表", "活动", "客户", "需求", "设计稿", "招聘", "预算")
    hits = [word for word in words if word in prompt]
    assert len(hits) >= 4, hits


def test_the_interviewer_must_name_the_company_and_quote_only_what_was_said():
    # Three rules a live run broke: the opening left out the company, a follow-up cited a bank
    # question as something the candidate had said, and a reply asked two questions.
    from jc.skills.loader import require_skill

    body = require_skill("coach-mock").body
    assert "公司名和岗位名必须都说出来" in body
    assert "本场亲口说过的话" in body
    assert "一条消息里只能有一个问句" in body


def test_the_interviewer_says_the_closing_line_once_the_interview_is_ended():
    # E-07: the candidate ends the interview from the bar; the interviewer must say the closing
    # line itself, not leave it to the page.
    from jc.skills.loader import require_skill

    body = require_skill("coach-mock").body
    assert "必须用一两句话说出结束语" in body
    assert "报告由独立评审生成" in body
