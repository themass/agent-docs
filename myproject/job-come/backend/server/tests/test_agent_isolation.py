"""Agent isolation (AGENTS-DESIGN §3): each product's roles reach only their own skills and tools.

The rules are checked against the declarations the runtime actually uses (roles.SKILL_SCOPE and the
tool catalog), so a change that breaks isolation fails here rather than in production.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jc.agent.roles import SKILL_SCOPE
from jc.agent.tool_catalog import SKILL_TOOLS

SKILLS_ROOT = Path(__file__).resolve().parents[2] / "agent" / "skills"

# Which product each role belongs to. "shared" is a utility role any product may call as a tool.
PRODUCT_OF_ROLE = {
    "resume-coach": "resume",
    "profile-interview": "resume",
    "resume-writer": "resume",
    "resume-reviewer": "resume",
    "coach-mock": "interview",
    "coach-answer": "interview",
    "coach-archive": "interview",
    "interview-reviewer": "interview",
    "jd-parser": "shared",
    "apply-pipeline": "apply",
}

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


def _tools_of(role: str) -> set[str]:
    tools: set[str] = set()
    for skill in SKILL_SCOPE[role]:
        for entry in SKILL_TOOLS.get(skill, []):
            tools.add(entry if isinstance(entry, str) else entry["name"])
    return tools


def test_every_role_is_classified_to_a_product():
    assert set(SKILL_SCOPE) == set(PRODUCT_OF_ROLE), "a new role must declare its product"


@pytest.mark.parametrize("role", sorted(SKILL_SCOPE))
def test_a_role_reaches_only_skills_of_its_own_product(role):
    product = PRODUCT_OF_ROLE[role]
    for skill in SKILL_SCOPE[role]:
        owner = PRODUCT_OF_ROLE.get(skill)
        assert owner is not None, f"{role} reaches an unclassified skill {skill}"
        assert owner in {product, "shared"} or owner == product, (
            f"{role} ({product}) must not reach {skill} ({owner})"
        )


def test_the_apply_agent_holds_no_resume_skill():
    assert SKILL_SCOPE["apply-pipeline"] == frozenset({"apply-pipeline"})


@pytest.mark.parametrize("role", sorted(SKILL_SCOPE))
def test_a_role_holds_no_tool_of_another_product(role):
    product = PRODUCT_OF_ROLE[role]
    tools = _tools_of(role)
    for other, owned in PRODUCT_TOOLS.items():
        if other == product:
            continue
        leaked = tools & owned
        assert not leaked, f"{role} ({product}) holds {other} tools: {sorted(leaked)}"


def test_each_skill_id_exists_once_and_on_the_public_path():
    public = {p.name for p in (SKILLS_ROOT / "public").iterdir() if p.is_dir()}
    custom = {p.name for p in (SKILLS_ROOT / "custom").iterdir() if p.is_dir()}
    assert public & custom == set(), "a skill id must not exist in both public and custom"
    for skill in {s for scope in SKILL_SCOPE.values() for s in scope}:
        assert skill in public, f"{skill} is declared in a role scope but has no public package"


def test_reviewer_holds_exactly_the_read_and_report_tools():
    """The independent reviewer is a spectator: it may read the session and write the report,
    and nothing that asks the candidate a question or ends the session (AGENTS-DESIGN §4.2)."""
    assert SKILL_SCOPE["interview-reviewer"] == frozenset({"interview-reviewer"})
    assert _tools_of("interview-reviewer") == {
        "jc_profile_get",
        "jc_mock_session_history",
        "jc_mock_report_write",
    }
