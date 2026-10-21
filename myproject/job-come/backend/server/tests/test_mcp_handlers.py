"""MCP handler unit tests."""

from __future__ import annotations

from jc.agent.tool_catalog import SKILL_TOOLS, tools_for_skill


def test_apply_pipeline_tool_registered() -> None:
    names = {t["function"]["name"] for t in tools_for_skill("apply-pipeline")}
    assert "jc_apply_pipeline" in names
    assert "jc_fit_score" in names
    assert "jc_resume_review" in names


def test_resume_reviewer_skill_has_review_tool() -> None:
    assert "jc_resume_review" in SKILL_TOOLS["resume-reviewer"]
    assert "jc_resume_review" in SKILL_TOOLS["resume-writer"]


def test_coach_mock_has_answer_save_attempt() -> None:
    assert "jc_answer_save_attempt" in SKILL_TOOLS["coach-mock"]
    assert "jc_question_upsert" in SKILL_TOOLS["coach-mock"]


