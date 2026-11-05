"""Evidence-gap detection: ask the user for the missing proof instead of inventing it."""

from jc.schemas.profile_payload import (
    ProfileContact,
    ProfileExperience,
    ProfileLink,
    ProfilePayload,
    ProfileProject,
)
from jc.services.evidence_gaps import find_evidence_gaps


def _exp(
    *highlights: str, title: str = "高级产品经理", company: str = "某公司"
) -> ProfileExperience:
    return ProfileExperience(
        id="e1",
        company=company,
        title=title,
        start_date="2020-01",
        highlights=list(highlights),
    )


def test_a_fully_quantified_bullet_raises_no_question() -> None:
    """We must not nag about bullets that are already strong."""
    profile = ProfilePayload(experiences=[_exp("主导会员体系改版，付费转化提升 3.2%")])
    assert find_evidence_gaps(profile, job_title="高级产品经理") == []


def test_vague_quantifier_is_asked_for_a_real_number() -> None:
    profile = ProfilePayload(experiences=[_exp("参与多项需求的设计与落地，推动按期交付")])
    gaps = find_evidence_gaps(profile, job_title="高级产品经理")
    assert [g.kind for g in gaps] == ["vague_quantity"]
    assert "多项" in gaps[0].question
    assert gaps[0].field_path == "experiences[0].highlights[0]"


def test_weak_lead_verb_asks_about_real_ownership_without_assuming_it() -> None:
    """The question must not presume the user led the work — that is the whole point."""
    profile = ProfilePayload(experiences=[_exp("参与统一配置中心的建设与推广工作")])
    gaps = find_evidence_gaps(profile, job_title="后端工程师")
    assert gaps[0].kind == "weak_ownership"
    assert "配合他人" in gaps[0].question
    assert "主导" not in gaps[0].question


def test_missing_outcome_asks_for_a_metric_in_quantitative_roles() -> None:
    profile = ProfilePayload(
        experiences=[_exp("重构订单服务的履约模块并完成灰度发布", title="后端工程师")]
    )
    gaps = find_evidence_gaps(profile, job_title="后端工程师")
    assert gaps[0].kind == "missing_outcome"
    assert "数字" in gaps[0].question


def test_missing_outcome_does_not_demand_a_metric_in_non_quantitative_roles() -> None:
    """Legal/HR/finance outcomes are often 'the bad thing did not happen'.

    Demanding a number here is the engineering bias this module exists to remove.
    """
    profile = ProfilePayload(
        experiences=[_exp("负责公司商业合同的审核与谈判支持", title="法务经理")]
    )
    gaps = find_evidence_gaps(profile, job_title="法务经理")
    assert gaps[0].kind == "missing_outcome"
    assert "没有数字也没关系" in gaps[0].question
    assert "避免了什么风险" in gaps[0].question


def test_thin_bullet_is_asked_for_object_and_result() -> None:
    profile = ProfilePayload(experiences=[_exp("优化流程")])
    gaps = find_evidence_gaps(profile, job_title="运营专家")
    assert gaps[0].kind == "thin_bullet"


def test_recent_role_gaps_outrank_older_ones() -> None:
    """The most recent role is read most closely, so its gaps cost the most."""
    profile = ProfilePayload(
        experiences=[
            _exp("重构订单服务的履约模块并完成灰度发布", title="后端工程师", company="近期公司"),
            ProfileExperience(
                id="e2",
                company="早期公司",
                title="后端工程师",
                start_date="2016-01",
                end_date="2019-12",
                highlights=["维护内部结算服务并处理日常需求"],
            ),
        ]
    )
    gaps = find_evidence_gaps(profile, job_title="后端工程师")
    assert gaps[0].source_text.startswith("重构订单服务")
    assert gaps[0].weight > gaps[-1].weight


def test_empty_experience_is_the_highest_priority_question() -> None:
    profile = ProfilePayload(
        experiences=[
            ProfileExperience(id="e1", company="某公司", title="产品经理", start_date="2021-01")
        ]
    )
    gaps = find_evidence_gaps(profile, job_title="产品经理")
    assert gaps[0].kind == "empty_experience"
    assert gaps[0].field_path == "experiences[0]"


def test_projects_are_examined_too() -> None:
    profile = ProfilePayload(
        projects=[ProfileProject(id="p1", name="统一配置中心", highlights=["参与方案设计与评审"])]
    )
    gaps = find_evidence_gaps(profile, job_title="后端工程师")
    assert gaps[0].field_path == "projects[0].highlights[0]"


def test_project_with_only_a_name_is_flagged() -> None:
    profile = ProfilePayload(projects=[ProfileProject(id="p1", name="统一配置中心")])
    gaps = find_evidence_gaps(profile, job_title="后端工程师")
    assert [g.kind for g in gaps] == ["empty_project"]


def test_design_role_is_asked_for_a_portfolio_link() -> None:
    """A role-specific document requirement a generic reviewer has no way to know."""
    profile = ProfilePayload(
        experiences=[_exp("主导品牌视觉升级，覆盖 12 个触点", title="视觉设计师")]
    )
    gaps = find_evidence_gaps(profile, job_title="视觉设计师")
    assert gaps[0].kind == "missing_must_have"
    assert "作品集" in gaps[0].question


def test_portfolio_question_disappears_once_a_link_exists() -> None:
    profile = ProfilePayload(
        contact=ProfileContact(links=[ProfileLink(type="portfolio", url="https://example.com/portfolio")]),
        experiences=[_exp("主导品牌视觉升级，覆盖 12 个触点", title="视觉设计师")],
    )
    assert find_evidence_gaps(profile, job_title="视觉设计师") == []


def test_explicit_role_family_overrides_title_inference() -> None:
    """The user must be able to correct a wrong guess."""
    profile = ProfilePayload(
        experiences=[_exp("负责公司商业合同的审核与谈判支持", title="某个奇怪的头衔")]
    )
    quant = find_evidence_gaps(profile, role_family="backend")
    non_quant = find_evidence_gaps(profile, role_family="legal")
    assert "数字" in quant[0].question
    assert "没有数字也没关系" in non_quant[0].question


def test_limit_is_respected_and_ordering_is_by_weight() -> None:
    profile = ProfilePayload(
        experiences=[_exp(*[f"参与多项工作 {i} 的推进与落地" for i in range(20)])]
    )
    gaps = find_evidence_gaps(profile, job_title="产品经理", limit=5)
    assert len(gaps) == 5
    assert [g.weight for g in gaps] == sorted((g.weight for g in gaps), reverse=True)


def test_no_question_ever_contains_a_fabricated_value() -> None:
    """A question may name a metric *type*; it must never supply the value."""
    profile = ProfilePayload(
        experiences=[_exp("重构订单服务的履约模块并完成灰度发布", title="后端工程师")]
    )
    for gap in find_evidence_gaps(profile, job_title="后端工程师"):
        bare = gap.question.replace("（", "").replace("）", "")
        assert "%" not in bare or "提升 " not in gap.question
