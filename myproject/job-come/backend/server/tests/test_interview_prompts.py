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
