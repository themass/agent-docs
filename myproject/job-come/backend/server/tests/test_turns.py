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


def test_the_interview_message_names_the_bound_job_and_mock_session():
    ctx = TurnContext(db=None, profiles=None, actor=None, profile_id="p1", job_id="j1",
                      ui_context=None, default_skill="coach-mock")
    text = turn.TURN_PROVIDERS["mock_session"].message(
        ctx, {"mock_session_id": "ms1", "drawn_stems": []}, "coach-mock", "开始")
    assert "job_id=j1" in text and "ms1" in text
