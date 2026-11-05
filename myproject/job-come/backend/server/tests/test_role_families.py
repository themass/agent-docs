"""Role-family inference and playbook contracts."""

import pytest

from jc.domain.role_families import (
    GENERAL,
    PLAYBOOKS,
    all_families,
    get_playbook,
    infer_role_family,
    playbook_for_title,
    resolve_role_family,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("后端开发工程师", "backend"),
        ("资深 Golang 工程师", "backend"),
        ("前端开发专家", "frontend"),
        ("iOS 开发工程师", "ios"),
        ("SRE 工程师", "devops"),
        ("数据分析师", "data"),
        ("高级产品经理", "pm"),
        ("资深视觉设计师", "design"),
        ("用户增长运营", "operations"),
        ("品牌市场经理", "marketing"),
        ("大客户销售总监", "sales"),
        ("客户成功经理", "customer_success"),
        ("HRBP", "hr"),
        ("经营分析经理", "finance"),
        ("法务合规经理", "legal"),
        ("研发总监", "management"),
    ],
)
def test_infer_role_family_covers_knowledge_work(title: str, expected: str) -> None:
    assert infer_role_family(title) == expected


def test_specific_discipline_beats_generic_management() -> None:
    """`后端技术负责人` is a backend role, not a generic management role.

    `管理` aliases sit last in the alias table precisely so a seniority word in the title
    cannot override the actual discipline.
    """
    assert infer_role_family("后端技术负责人") == "backend"
    assert infer_role_family("前端团队负责人") == "frontend"


def test_unknown_title_falls_back_to_general_rather_than_guessing() -> None:
    """Guessing wrong rewrites the whole resume for the wrong audience."""
    assert infer_role_family("技术专家（底座方向）") == GENERAL
    assert infer_role_family("") == GENERAL
    assert infer_role_family(None) == GENERAL


def test_infer_tries_candidates_in_order() -> None:
    """The JD title is more authoritative than the candidate's last job title."""
    assert infer_role_family(None, "", "高级产品经理") == "pm"
    assert infer_role_family("数据分析师", "高级产品经理") == "data"


def test_playbook_for_title_returns_the_playbook_not_just_the_id() -> None:
    """Three services call this instead of chaining infer + get themselves.

    They need the playbook object, and they pass the same ordered candidate list as
    `infer_role_family`. If this ever stops honouring candidate order, the resume gets
    written against the wrong reader without anything failing loudly.
    """
    assert playbook_for_title("后端开发工程师").id == "backend"
    assert playbook_for_title(None, "", "高级产品经理").id == "pm"
    assert playbook_for_title("技术专家（底座方向）").id == GENERAL


def test_get_playbook_is_total() -> None:
    """An unknown or hostile family id must not raise; it degrades to neutral."""
    assert get_playbook("no_such_family").id == GENERAL
    assert get_playbook(None).id == GENERAL
    assert get_playbook("  BACKEND  ").id == "backend"


def test_every_playbook_declares_outcomes_and_objects() -> None:
    """A playbook with no vocabulary provides no guidance and would silently weaken output."""
    for family, pb in PLAYBOOKS.items():
        assert pb.id == family
        assert pb.outcome_metrics, f"{family} has no outcome vocabulary"
        assert pb.object_nouns, f"{family} has no object vocabulary"
        assert set(pb.section_priority) == {
            "summary",
            "experience",
            "projects",
            "education",
            "skills",
        }, f"{family} section_priority must be a permutation of the known sections"


def test_non_quantitative_roles_are_marked_as_such() -> None:
    """These roles legitimately produce outcomes with no number attached.

    Demanding a metric here produces a false 'missing outcome' warning, which is how the
    engineering-tuned methodology used to penalise non-engineering users.
    """
    for family in ("legal", "hr", "finance", "design", GENERAL):
        assert PLAYBOOKS[family].quantification_optional is True
    for family in ("backend", "data", "sales", "marketing"):
        assert PLAYBOOKS[family].quantification_optional is False


def test_design_resume_requires_a_portfolio() -> None:
    must = " ".join(PLAYBOOKS["design"].must_haves)
    assert "作品集" in must


def test_sales_and_design_reorder_sections_for_their_readers() -> None:
    assert PLAYBOOKS["design"].section_priority[1] == "projects"
    assert PLAYBOOKS["sales"].section_priority.index("skills") < PLAYBOOKS[
        "sales"
    ].section_priority.index("projects")


def test_management_playbook_warns_about_claiming_team_work() -> None:
    """The most common way a senior manager's resume loses credibility."""
    angles = " ".join(PLAYBOOKS["management"].framing_angles)
    assert "个人" in angles and "团队" in angles


def test_prompt_block_never_leaks_fabrication_permission() -> None:
    for pb in PLAYBOOKS.values():
        block = pb.as_prompt_block()
        assert pb.label in block
        assert "Section priority:" in block
        if pb.quantification_optional:
            assert "never invent" in block


def test_all_families_catalogue_is_ui_ready() -> None:
    families = all_families()
    assert len(families) == len(PLAYBOOKS)
    general = [f for f in families if f["id"] == GENERAL]
    assert general and general[0]["label"]
    for item in families:
        assert item["outcome_metrics"]


def test_resolve_prefers_user_override_over_everything() -> None:
    """A wrong guess rewrites the whole resume for the wrong reader, so the user wins."""
    assert (
        resolve_role_family(
            override="design",
            job_category="backend",
            job_title="后端工程师",
            profile_titles=("后端工程师",),
        )
        == "design"
    )


def test_resolve_falls_back_from_stored_category_to_titles() -> None:
    assert resolve_role_family(job_category="data", job_title="后端工程师") == "data"
    assert resolve_role_family(job_title="数据分析师") == "data"
    assert resolve_role_family(profile_titles=("前端工程师",)) == "frontend"


def test_resolve_ignores_unknown_ids_rather_than_trusting_them() -> None:
    assert resolve_role_family(override="bogus", job_title="iOS 工程师") == "ios"
    assert resolve_role_family(override="bogus") == "general"
