"""Document-level composition: ordering, scope lines, and conclusion-first summaries.

The invariant under test: composition may move sections, never source paragraphs or
sentences inside a project. Scoring provides advice, not an automatic narrative sort.
"""

from __future__ import annotations

from typing import Any

from jc.domain.role_families import get_playbook
from jc.services.resume_structure import (
    analyze_summary,
    audit_structure,
    compose_document,
    resolve_section_order,
    score_bullet,
)

_BACKEND = get_playbook("backend")
_LEGAL = get_playbook("legal")


def _score(text: str, playbook: Any = _BACKEND, **kwargs: Any) -> float:
    return score_bullet(text, playbook=playbook, **kwargs).score


# --- bullet strength ------------------------------------------------------------------


def test_quantified_outcome_outranks_bare_responsibility() -> None:
    strong = _score("搭建统一配置中心，覆盖 120 多个服务，配置变更事故下降 70%")
    weak = _score("负责后端开发相关工作")
    assert strong > weak
    assert strong >= 4.0
    assert weak < 4.0


def test_weak_verbs_are_penalised_and_named() -> None:
    """The reason strings are shown to the user, so they have to be accurate."""
    result = score_bullet("参与大促容量保障", playbook=_BACKEND)
    assert "动词偏弱" in result.reasons
    assert result.score < 0


def test_calendar_years_do_not_count_as_quantification() -> None:
    """`2021-03 加入团队` carries no evidence; counting the year would rank it as proof."""
    dated = score_bullet("2021 年加入订单团队", playbook=_BACKEND)
    assert "带量化" not in dated.reasons


def test_qualitative_roles_are_not_ranked_below_noise() -> None:
    """Legal/HR/finance outcomes are often unnumbered, and must still beat a duty line.

    The bullet below carries no outcome verb and no metric — it is simply a precise
    statement of real work, which is what a good legal bullet often looks like. Without
    the `quantification_optional` allowance it scored at or below a duty line and got
    sorted to the bottom of its block, burying the best evidence the role had.
    """
    precise = "独立负责数据合规审查与跨境传输方案的法律意见"
    duty = "负责合规相关工作"
    assert _score(precise, _LEGAL) > _score(duty, _LEGAL)
    # The allowance is what makes the difference, so the same sentence scores lower
    # under a playbook that expects numbers.
    assert _score(precise, _LEGAL) > _score(precise, _BACKEND)


def test_job_keywords_lift_relevant_bullets() -> None:
    plain = _score("主导服务拆分，发布耗时下降 85%")
    matched = _score("主导服务拆分，发布耗时下降 85%", job_keywords=("服务拆分",))
    assert matched > plain


# --- ordering -------------------------------------------------------------------------


def test_bullet_strength_does_not_override_source_narrative_order() -> None:
    weak = "负责日常维护"
    strong = "主导订单服务拆分为 6 个微服务，发布耗时从 40 分钟降到 6 分钟"
    sections = {
        "role_family": "backend",
        "experience_blocks": [
            {
                "company": "A",
                "title": "工程师",
                "scope_line": "负责订单链路",
                "bullets": [weak, strong],
            }
        ],
    }
    report = compose_document(sections, role_family="backend")
    bullets = sections["experience_blocks"][0]["bullets"]
    assert bullets == [weak, strong]
    assert set(bullets) == {weak, strong}
    assert report.moves == []


def test_equal_strength_keeps_source_order_and_reports_nothing() -> None:
    """A block the writer already ordered well must be left alone.

    Reporting a move the reader cannot perceive trains them to ignore the change list.
    """
    bullets = [
        "主导配置中心建设，覆盖 120 个服务，事故下降 70%",
        "主导灰度发布改造，覆盖 110 个服务，事故下降 60%",
    ]
    sections = {
        "experience_blocks": [
            {"company": "A", "title": "工程师", "scope_line": "x", "bullets": list(bullets)}
        ]
    }
    report = compose_document(sections, role_family="backend")
    assert sections["experience_blocks"][0]["bullets"] == bullets
    assert report.moves == []


def test_section_order_change_is_only_reported_when_content_drove_it() -> None:
    """Normalising a model's arbitrary order back to the role default is housekeeping."""
    sections = {
        "section_order": ["skills", "summary", "experience"],
        "experience_blocks": [
            {
                "company": "A",
                "title": "工程师",
                "scope_line": "x",
                "bullets": ["主导拆分，耗时降 85%"],
            }
        ],
    }
    report = compose_document(sections, role_family="backend")
    assert report.section_order_changed is False
    assert report.section_order_reason is None
    assert sections["section_order"][0] == "summary"


def test_projects_are_promoted_only_by_a_clear_margin() -> None:
    playbook = _BACKEND
    weak_exp = {
        "experience_blocks": [{"bullets": ["负责开发工作"]}],
        "project_blocks": [
            {"bullets": ["主导配置中心建设，覆盖 120 个服务，配置事故下降 70%"]}
        ],
    }
    order, reason = resolve_section_order(weak_exp, playbook=playbook)
    assert order.index("projects") < order.index("experience")
    assert reason and "项目经历" in reason

    even = {
        "experience_blocks": [
            {"bullets": ["主导订单拆分，发布耗时下降 85%，覆盖 6 个服务"]}
        ],
        "project_blocks": [
            {"bullets": ["主导配置中心建设，覆盖 120 个服务，事故下降 70%"]}
        ],
    }
    order, reason = resolve_section_order(even, playbook=playbook)
    assert order.index("experience") < order.index("projects")
    assert reason is None


def test_no_projects_means_no_promotion_decision() -> None:
    order, reason = resolve_section_order(
        {"experience_blocks": [{"bullets": ["负责开发"]}]}, playbook=_BACKEND
    )
    assert reason is None
    assert order.index("experience") < order.index("projects")


# --- summary --------------------------------------------------------------------------


def test_conclusion_first_summary_is_recognised() -> None:
    shape = analyze_summary(
        "8 年后端工程师，主导订单系统拆分，支撑日均 1200 万单，希望继续做基础架构方向。",
        headline="后端技术专家",
    )
    assert shape.present and shape.positioning and shape.evidence
    assert shape.conclusion_first
    assert shape.direction


def test_duty_summary_is_not_conclusion_first() -> None:
    shape = analyze_summary("本人负责后端开发，熟悉 Java、微服务与数据库。")
    assert shape.present
    assert not shape.conclusion_first


def test_missing_summary_is_reported_as_its_own_defect() -> None:
    report = compose_document({"experience_blocks": []}, role_family="backend")
    codes = {issue.code for issue in report.issues}
    assert "missing_summary" in codes


# --- issues and auditing --------------------------------------------------------------


def test_missing_scope_line_is_reported_per_role() -> None:
    sections = {
        "summary": "8 年后端工程师，主导拆分，支撑日均 1200 万单。",
        "experience_blocks": [
            {"company": "A 公司", "title": "工程师", "bullets": ["主导拆分，耗时降 85%"]}
        ],
    }
    report = compose_document(sections, role_family="backend")
    scope_issues = [i for i in report.issues if i.code == "missing_scope_line"]
    assert len(scope_issues) == 1
    assert "A 公司" in scope_issues[0].message
    assert report.scope_lines == 0
    assert report.blocks_total == 1


def test_audit_does_not_mutate_the_draft_it_reads() -> None:
    """Export-time auditing runs on a stored draft; reordering it there would make the
    downloaded file differ from the one the user approved on screen."""
    bullets = ["负责日常维护", "主导拆分，发布耗时下降 85%"]
    sections = {
        "role_family": "backend",
        "experience_blocks": [{"company": "A", "title": "工程师", "bullets": list(bullets)}],
    }
    report = audit_structure(sections)
    assert sections["experience_blocks"][0]["bullets"] == bullets
    assert "section_order" not in sections
    assert report.moves == []


def test_report_round_trips_to_a_json_safe_dict() -> None:
    sections = {
        "summary": "8 年后端工程师，主导拆分，支撑日均 1200 万单。",
        "experience_blocks": [
            {
                "company": "A",
                "title": "工程师",
                "scope_line": "带 8 人团队",
                "bullets": ["负责维护", "主导拆分，耗时降 85%"],
            }
        ],
    }
    data = compose_document(sections, role_family="backend").to_dict()
    assert set(data) == {
        "section_order",
        "section_order_changed",
        "section_order_reason",
        "moves",
        "scope_lines",
        "blocks_total",
        "summary_shape",
        "issues",
    }
    assert data["summary_shape"]["conclusion_first"] is True
    assert data["moves"] == []
    assert sections["experience_blocks"][0]["bullets"] == ["负责维护", "主导拆分，耗时降 85%"]
