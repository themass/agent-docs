"""A turn's skill is decided by its role's switch rules, and its context by its role's provider.

Both are named in roles.yaml and resolved through the registries in `jc.agent.turn`. These tests
pin the decisions, not the providers' database reads, which the mock-flow tests cover.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jc.agent import turn
from jc.agent.roles import role
from jc.agent.turn import TurnContext, facts_common, resolve_turn_skill


def _with_plan(monkeypatch, can_generate: bool) -> None:
    monkeypatch.setattr(turn, "build_intake_plan",
                        lambda payload: SimpleNamespace(can_generate=can_generate))


def test_a_profile_that_cannot_generate_yet_runs_the_interview_skill(monkeypatch):
    _with_plan(monkeypatch, can_generate=False)
    facts = {"profile_payload": object()}
    assert resolve_turn_skill(role("resume-coach"), facts) == "profile-interview"


def test_a_profile_that_can_generate_runs_the_default_skill(monkeypatch):
    _with_plan(monkeypatch, can_generate=True)
    facts = {"profile_payload": object()}
    assert resolve_turn_skill(role("resume-coach"), facts) == "resume-coach"


def test_no_profile_is_no_switch(monkeypatch):
    _with_plan(monkeypatch, can_generate=False)
    assert resolve_turn_skill(role("resume-coach"), {"profile_payload": None}) == "resume-coach"


def test_an_archive_intent_runs_the_archive_skill_of_the_interview_role():
    assert resolve_turn_skill(role("coach-mock"), {"intent": "archive"}) == "coach-archive"


def test_without_intent_the_interview_role_runs_its_practice_skill():
    assert resolve_turn_skill(role("coach-mock"), facts_common(None)) == "coach-mock"


def test_a_role_without_switch_rules_always_runs_its_default_skill():
    assert resolve_turn_skill(role("apply-pipeline"), {"intent": "archive"}) == "apply-pipeline"


def test_the_intent_fact_comes_from_the_page_and_is_absent_otherwise():
    assert facts_common(SimpleNamespace(intent="archive")) == {"intent": "archive"}
    assert facts_common(None) == {"intent": None}


@pytest.mark.asyncio
async def test_the_resume_provider_reports_no_facts_without_a_profile():
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id=None, job_id=None,
                      ui_context=None, default_skill="resume-coach")
    assert await turn.TURN_PROVIDERS["resume_profile"].gather(ctx) == {}


def test_the_resume_provider_passes_the_text_through_without_a_profile():
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id=None, job_id=None,
                      ui_context=None, default_skill="resume-coach")
    text = turn.TURN_PROVIDERS["resume_profile"].message(ctx, {}, "resume-coach", "改一下")
    assert text == "改一下"


def test_a_switched_skill_of_the_interview_role_gets_its_text_without_mock_state():
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    text = turn.TURN_PROVIDERS["mock_session"].message(
        ctx, {"mock_session_id": "ms1", "drawn_stems": ["题"]}, "coach-archive", "我面了一场")
    assert text == "我面了一场"


def test_the_interview_message_names_the_bound_job_and_mock_session():
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    text = turn.TURN_PROVIDERS["mock_session"].message(
        ctx, {"mock_session_id": "ms1", "drawn_stems": []}, "coach-mock", "开始")
    assert "job_id=j1" in text and "ms1" in text


def test_the_interview_message_does_not_forbid_the_interviewer_to_introduce_themselves():
    # A real interviewer opens with a greeting and asks for a self-introduction; the wrapper once
    # told the agent not to introduce itself, which kept the first turn mechanical.
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    text = turn.TURN_PROVIDERS["mock_session"].message(
        ctx, {"mock_session_id": "ms1", "drawn_stems": []}, "coach-mock", "开始")
    assert "不要自我介绍" not in text
    assert "面试官" in text


def test_the_interview_message_states_level_depth_and_follow_up_direction():
    from jc.coach.level import LEVEL_SPECS

    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    text = turn.TURN_PROVIDERS["mock_session"].message(
        ctx, {"mock_session_id": "ms1", "drawn_stems": [], "level": "mid"}, "coach-mock", "开始")
    spec = LEVEL_SPECS["mid"]
    assert "中级" in text and "P6" in text
    assert spec.depth in text and spec.follow_up in text
    assert "评分标准不随级别变化" in text


def test_a_session_without_a_level_adds_no_level_line():
    # Sessions created before levels existed have none.
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    text = turn.TURN_PROVIDERS["mock_session"].message(
        ctx, {"mock_session_id": "ms1", "drawn_stems": [], "level": None}, "coach-mock", "开始")
    assert "面试级别" not in text


def test_the_interview_message_names_only_tools_the_interviewer_holds():
    # The task text once told the interviewer to call tools its skill no longer allowed.
    import re

    from jc.skills.loader import require_skill

    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    for drawn in ([], ["一道题库题"]):
        text = turn.TURN_PROVIDERS["mock_session"].message(
            ctx, {"mock_session_id": "ms1", "drawn_stems": drawn, "level": "mid"},
            "coach-mock", "开始")
        named = set(re.findall(r"jc_[a-z_]+", text))
        held = set(require_skill("coach-mock").allowed_tools)
        assert named, "the task text should name the tools it relies on"
        assert named <= held, f"names tools the skill does not allow: {sorted(named - held)}"


def test_the_interviewer_is_told_what_an_unregistered_question_does_to_the_record():
    # The system records every message as the answer to the last registered question. A question the
    # interviewer asks without registering it would put the next real answer under the wrong one.
    from jc.skills.loader import require_skill

    body = require_skill("coach-mock").body
    assert "没有登记" in body and "记在上一题名下" in body


def test_the_reviewer_is_told_an_answer_may_hold_more_than_the_answer():
    from jc.skills.loader import require_skill

    body = require_skill("interview-reviewer").body
    assert "没听清" in body and "不当作回答内容" in body
