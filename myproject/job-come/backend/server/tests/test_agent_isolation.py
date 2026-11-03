"""Agent isolation (AGENTS-DESIGN §3): each product's roles hold only their own tools.

The rules are checked against the declaration the runtime actually uses (`roles.yaml`, through
`jc.agent.roles`), so a change that breaks isolation fails here rather than in production.
`PRODUCT_TOOLS` below is deliberately kept apart from it: it is the independent statement of which
product owns which tool, and the roles are checked against it.
"""

from __future__ import annotations

import pytest

from jc.agent.roles import roles

# Tools that belong to one product. A role of another product must never hold them.
PRODUCT_TOOLS = {
    "resume": {"jc_resume_review", "jc_profile_photo_set", "jc_intake_plan", "jc_intake_record"},
    "interview": {
        "jc_bank_search_questions", "jc_question_upsert", "jc_answer_save_attempt",
        "jc_mock_session_history", "jc_interview_save", "jc_mock_report_write",
        "jc_mock_plan", "jc_mock_ask", "jc_mock_end", "jc_mock_review",
    },
    # jc_fit_score is job analysis shared with the 定向岗位 page, so it is not apply-owned.
    "apply": {"jc_apply_pipeline"},
}


def _tools_of(role_id: str) -> set[str]:
    return set(roles()[role_id].tools)


@pytest.mark.parametrize("role_id", sorted(roles()))
def test_a_role_holds_no_tool_of_another_product(role_id):
    product = roles()[role_id].product
    tools = _tools_of(role_id)
    for other, owned in PRODUCT_TOOLS.items():
        if other == product:
            continue
        leaked = tools & owned
        assert not leaked, f"{role_id} ({product}) holds {other} tools: {sorted(leaked)}"


def test_the_apply_agent_holds_no_resume_tool_and_swaps_to_nothing():
    apply = roles()["apply-pipeline"]
    assert not set(apply.tools) & PRODUCT_TOOLS["resume"]
    assert apply.swap_to == () and apply.delegates == ()


def test_reviewer_holds_exactly_the_read_and_report_tools():
    """The independent reviewer is a spectator: it may read the session and write the report,
    and nothing that asks the candidate a question or ends the session (AGENTS-DESIGN §4.2)."""
    assert _tools_of("interview-reviewer") == {
        "jc_profile_get",
        "jc_mock_session_history",
        "jc_mock_report_write",
    }
