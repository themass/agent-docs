"""Delegation is for runs that need another agent's judgment mid-turn.

Everything else runs as one main agent.

These tests pin the rules that keep a delegated run inside its own role: which skill may delegate,
to whom, with which tools, and that `task` is offered to no other run.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from jc.adapters.deerflow_harness_client import DELEGATES, delegates_for_skill
from jc.agent.tool_catalog import SKILL_TOOLS

BACKEND = Path(__file__).resolve().parents[2]

# Tools that put a question to the candidate or change interview state. A delegated reviewer must
# hold none of them, whatever its config says.
CANDIDATE_FACING = {
    "jc_mock_ask", "jc_mock_end", "jc_mock_plan", "jc_question_upsert",
    "jc_answer_save_attempt", "jc_interview_save",
}


def _custom_agents() -> dict:
    config = yaml.safe_load((BACKEND / "agent" / "deerflow" / "config.yaml").read_text("utf-8"))
    return config["subagents"]["custom_agents"]


def test_only_the_interview_coach_delegates_and_only_to_the_reviewer():
    assert DELEGATES == {"coach-mock": frozenset({"interview-reviewer"})}
    assert delegates_for_skill("coach-mock") == {"interview-reviewer"}
    for skill in ("resume-coach", "resume-writer", "interview-reviewer", "apply-pipeline"):
        assert delegates_for_skill(skill) == frozenset(), skill


def test_each_delegate_is_a_declared_subagent_with_a_matching_role():
    custom = _custom_agents()
    for skill, targets in DELEGATES.items():
        for target in targets:
            assert target in custom, f"{skill} delegates to undeclared subagent {target}"
            assert custom[target]["system_prompt"] == f"skill:{target}"


def test_the_reviewer_subagent_holds_only_its_own_skill_tools():
    reviewer = _custom_agents()["interview-reviewer"]
    assert set(reviewer["tools"]) <= set(SKILL_TOOLS["interview-reviewer"])
    assert not set(reviewer["tools"]) & CANDIDATE_FACING
    assert reviewer["skills"] == ["interview-reviewer"]
    assert reviewer["model"] == "jc-reviewer"


def test_no_subagent_can_reach_the_framework_task_tool_itself():
    # `task` is added by the harness per run, never through a subagent's own allowlist, so a
    # delegated run cannot delegate again.
    for name, spec in _custom_agents().items():
        assert "task" not in spec["tools"], name

