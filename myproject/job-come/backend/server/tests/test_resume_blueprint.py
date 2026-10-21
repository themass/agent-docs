"""The per-family document bar, and whether it measures what it claims to."""

from __future__ import annotations

from typing import Any

from jc.domain.role_families import PLAYBOOKS
from jc.services.resume_blueprint import (
    REQUIREMENT_IDS,
    all_blueprints,
    blueprint_for,
    evaluate_blueprint,
)


def _finding(report: Any, requirement_id: str) -> Any:
    for finding in report.findings:
        if finding.requirement.id == requirement_id:
            return finding
    raise AssertionError(f"no finding for {requirement_id}")


def _strong_sections(**overrides: Any) -> dict[str, Any]:
    sections: dict[str, Any] = {
        "role_family": "backend",
        "header": {"name": "张三", "headline": "后端技术专家"},
        "summary": (
            "8 年后端工程师，主导订单系统拆分，支撑日均 1200 万单，"
            "希望继续做基础架构方向。"
        ),
        "experience_blocks": [
            {
                "company": "A 公司",
                "title": "技术专家",
                "scope_line": "带 8 人后端团队，负责订单与结算两条主链路",
                "bullets": [
                    "主导订单服务从单体拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟",
                    "搭建统一配置中心，覆盖 120 多个服务，配置变更事故下降 70%",
                    "设计跨服务补偿事务方案，解决分布式一致性问题，资金差错归零",
                    "牵头容量保障体系建设，支撑大促峰值流量，全程零线上事故",
                ],
            }
        ],
        "project_blocks": [],
    }
    sections.update(overrides)
    return sections


def test_every_family_has_a_usable_blueprint() -> None:
    """Derivation must cover all 16 families, so a new family needs no new table row."""
    catalogue = all_blueprints()
    assert len(catalogue) == len(PLAYBOOKS)
    for item in catalogue:
        assert item["summary_formula"] and len(item["summary_formula"]) == 3
        assert item["scope_dimensions"], item["family"]
        assert item["evidence_ladder"], item["family"]
        assert item["anti_patterns"], item["family"]
        assert item["lead_bullets"] >= 4
        assert 0.0 < item["outcome_ratio"] <= 1.0


def test_families_differ_in_what_they_demand() -> None:
    """The product promises per-role methodology; identical bars would make that a lie."""
    backend = blueprint_for("backend")
    legal = blueprint_for("legal")
    management = blueprint_for("management")

    assert backend.scope_dimensions != legal.scope_dimensions
    assert backend.evidence_ladder != legal.evidence_ladder
    # Qualitative-outcome roles get a lower density bar, never an exemption.
    assert legal.outcome_ratio < backend.outcome_ratio
    assert legal.outcome_ratio > 0
    # A management resume is judged on more of the record than an IC one.
    assert management.lead_bullets > backend.lead_bullets


def test_section_order_follows_the_family_playbook() -> None:
    """The blueprint must not invent its own reading order."""
    for family, playbook in PLAYBOOKS.items():
        assert blueprint_for(family).section_order == playbook.section_priority


def test_a_strong_document_meets_every_requirement() -> None:
    report = evaluate_blueprint(_strong_sections())
    unmet = [f.requirement.id for f in report.findings if not f.met]
    assert unmet == [], unmet
    assert report.met == report.total
    assert report.unmet_issues() == []


def test_duty_list_fails_on_outcomes_and_depth_not_on_honesty() -> None:
    """The classic weak resume: real job, nothing measurable, two lines per role."""
    report = evaluate_blueprint(
        _strong_sections(
            summary="本人负责后端开发相关工作，熟悉 Java 和微服务。",
            experience_blocks=[
                {
                    "company": "A 公司",
                    "title": "后端工程师",
                    "scope_line": None,
                    "bullets": ["负责后端开发相关工作", "参与系统维护"],
                }
            ],
        )
    )
    unmet = {f.requirement.id for f in report.findings if not f.met}
    assert "summary_conclusion_first" in unmet
    assert "scope_lines" in unmet
    assert "document_depth" in unmet
    assert "outcome_density" in unmet
    assert "strong_lead_bullets" in unmet


def test_findings_name_a_field_and_an_action() -> None:
    """A checklist item the user cannot act on is noise.

    Every unmet requirement has to say where the problem is and what to do, because the
    user reads this list instead of reading our methodology document.
    """
    report = evaluate_blueprint(
        _strong_sections(summary="", experience_blocks=[
            {"company": "A", "title": "工程师", "scope_line": None, "bullets": ["负责开发"]}
        ])
    )
    for finding in report.findings:
        if finding.met:
            continue
        assert finding.field_path, finding.requirement.id
        assert finding.requirement.fix
        assert finding.detail


def test_unmet_requirements_are_advisory_only() -> None:
    """A document-shape preference must never be able to block an export.

    Export gating reads `severity`, and the历史 failure mode here was a deterministic
    check escalating to blocking and locking users out of their own resume.
    """
    report = evaluate_blueprint(
        _strong_sections(summary="", experience_blocks=[
            {"company": "A", "title": "工程师", "scope_line": None, "bullets": ["负责开发"]}
        ])
    )
    issues = report.unmet_issues()
    assert issues
    assert {i["severity"] for i in issues} == {"warning"}
    assert all(i["code"].startswith("blueprint_") for i in issues)
    assert all(i["code"][len("blueprint_"):] in REQUIREMENT_IDS for i in issues)


def test_must_haves_are_only_checked_where_the_family_has_them() -> None:
    """`family_must_haves` is conditional, so the checklist length is family-dependent."""
    design = evaluate_blueprint(_strong_sections(role_family="design"))
    backend = evaluate_blueprint(_strong_sections(role_family="backend"))
    design_ids = {f.requirement.id for f in design.findings}
    backend_ids = {f.requirement.id for f in backend.findings}
    if blueprint_for("design").must_haves:
        assert "family_must_haves" in design_ids
    if not blueprint_for("backend").must_haves:
        assert "family_must_haves" not in backend_ids


def test_bilingual_drafts_are_measured_on_the_chinese_track() -> None:
    """A bilingual wrapper carries no bullets of its own; measuring it would score zero."""
    zh = _strong_sections()
    report = evaluate_blueprint({"track": "bilingual", "zh_sections": zh})
    assert report.met == report.total


def test_projects_count_toward_depth_and_outcomes() -> None:
    """Project work is real work; excluding it would penalise project-heavy careers."""
    with_projects = _strong_sections(
        experience_blocks=[
            {
                "company": "A 公司",
                "title": "技术专家",
                "scope_line": "负责平台方向",
                "bullets": ["主导配置中心建设，覆盖 120 个服务，事故下降 70%"],
            }
        ],
        project_blocks=[
            {
                "name": "统一配置中心",
                "scope_line": "独立负责，服务 12 个团队",
                "bullets": ["设计灰度发布机制，将变更事故降低 70%"],
            }
        ],
    )
    report = evaluate_blueprint(with_projects)
    scope = _finding(report, "scope_lines")
    assert "2/2" in scope.detail
    outcomes = _finding(report, "outcome_density")
    assert "2/2" in outcomes.detail


def test_prompt_block_states_the_numbers_it_will_be_measured_on() -> None:
    """The writer is told the same contract the checker enforces.

    A prompt that advises in prose while the checker measures numbers produces drafts
    that read fine and fail the checklist, which the user sees as us contradicting
    ourselves.
    """
    blueprint = blueprint_for("management")
    block = blueprint.as_prompt_block()
    assert str(blueprint.lead_bullets) in block
    assert str(int(blueprint.outcome_ratio * 100)) in block
    for dimension in blueprint.scope_dimensions:
        assert dimension in block
    assert "never invent work" in block
    assert "advisory, not quotas" in block
    assert "never split a project" in block
