"""Delegation is for runs that need another agent's judgment mid-turn.

Everything else runs as one main agent. These tests pin the rules that keep a delegated run inside
its own role: which role may delegate, to whom, with which tools, and that no subagent can delegate
again.
"""

from __future__ import annotations

from jc.agent.roles import roles, skill, skills, subagent_specs

# Tools that put a question to the candidate or change interview state. A delegated reviewer must
# hold none of them, whatever the declaration says.
CANDIDATE_FACING = {
    "jc_mock_ask", "jc_mock_end", "jc_mock_plan", "jc_question_upsert",
    "jc_answer_save_attempt", "jc_interview_save",
}


def test_only_the_interview_coach_delegates_and_only_to_the_reviewer():
    delegating = {s.id: set(s.delegates) for s in skills().values() if s.delegates}
    assert delegating == {"coach-mock": {"interview-reviewer"}}


def test_each_delegate_is_a_subagent_spec_whose_prompt_points_at_its_skill():
    specs = subagent_specs()
    for declared in skills().values():
        for target in declared.delegates:
            assert specs[target]["system_prompt"] == f"skill:{target}"


def test_the_reviewer_subagent_holds_only_its_own_tools_and_model():
    spec = subagent_specs()["interview-reviewer"]
    assert set(spec["tools"]) == set(skill("interview-reviewer").tools)
    assert not set(spec["tools"]) & CANDIDATE_FACING
    assert spec["skills"] == ["interview-reviewer"]
    assert spec["model"] == "jc-reviewer"


def test_every_subtask_role_is_a_subagent_and_nothing_else_is():
    assert set(subagent_specs()) == {r.id for r in roles().values() if r.mode == "subtask"}


def test_no_subagent_can_reach_the_framework_task_tool_itself():
    # `task` is added by the harness per run, never through a role's tools, so a delegated run
    # cannot delegate again.
    for declared in skills().values():
        assert "task" not in declared.tools, declared.id


def test_a_skill_of_the_same_role_without_delegates_does_not_get_the_task_tool():
    # Delegation belongs to the skill, not the role: recording a real interview shares the
    # interview coach's role, and must not be able to hand work to the reviewer.
    assert skill("coach-mock").delegates == ("interview-reviewer",)
    assert skill("coach-archive").delegates == ()
