"""Coverage audit: did the written resume keep what the career contains?"""

from jc.schemas.profile_payload import (
    ProfileExperience,
    ProfilePayload,
    ProfileProject,
)
from jc.services.resume_coverage import audit_coverage


def _profile(
    highlights: list[str],
    *,
    projects: list[ProfileProject] | None = None,
) -> ProfilePayload:
    return ProfilePayload(
        experiences=[
            ProfileExperience(
                id="e1",
                company="字节跳动",
                title="后端工程师",
                start_date="2020-01",
                highlights=highlights,
            )
        ],
        projects=projects or [],
    )


def _sections(bullets: list[str], *, projects: list[dict] | None = None) -> dict:
    return {
        "experience_blocks": [
            {"company": "字节跳动", "title": "后端工程师", "bullets": bullets}
        ],
        "project_blocks": projects or [],
    }


def test_a_rewritten_bullet_still_counts_as_covered() -> None:
    """The whole point of the writer is that the wording changes."""
    profile = _profile(["负责订单服务的拆分，把单体拆成微服务"])
    report = audit_coverage(
        _sections(["主导订单服务从单体拆分为 6 个微服务，发布耗时下降 70%"]), profile
    )
    assert report.dropped == []
    assert report.ratio == 1.0


def test_a_dropped_highlight_is_named_so_the_user_can_judge() -> None:
    profile = _profile(
        [
            "主导订单服务拆分，发布耗时从 40 分钟降到 6 分钟",
            "搭建全链路压测平台，覆盖 12 条核心交易链路",
        ]
    )
    report = audit_coverage(
        _sections(["主导订单服务拆分，发布耗时从 40 分钟降到 6 分钟"]), profile
    )
    assert len(report.dropped) == 1
    assert "全链路压测" in report.dropped[0].text
    assert report.dropped[0].where == "字节跳动 · 后端工程师"
    assert report.covered == 1
    assert report.source_highlights == 2
    # The note counts what is *missing*, not our covered/total bookkeeping: the user has
    # no way to know what a 「经历要点」is or what the denominator counted, so the earlier
    # 「只覆盖了 1 条」phrasing told them a number and no action.
    assert any("这 1 条经历没有写进" in n for n in report.notes)
    assert any("全链路压测" in n for n in report.notes)


def test_two_different_bullets_from_one_role_do_not_cover_each_other() -> None:
    """Shared company vocabulary must not inflate the overlap score."""
    profile = _profile(["搭建全链路压测平台，覆盖 12 条核心交易链路"])
    report = audit_coverage(
        _sections(["主导订单服务拆分，发布耗时从 40 分钟降到 6 分钟"]), profile
    )
    assert len(report.dropped) == 1
    assert report.dropped[0].best_match < 0.42


def test_missing_project_blocks_is_reported_as_a_generation_defect() -> None:
    """An empty 项目经历 on a profile that has projects is never a judgement call."""
    profile = _profile(
        ["负责订单服务拆分"],
        projects=[
            ProfileProject(id="p1", name="交易中台重构", highlights=["设计补偿事务方案"])
        ],
    )
    report = audit_coverage(_sections(["主导订单服务拆分"]), profile)
    assert report.projects_missing is True
    assert any("没有项目经历这一节" in n for n in report.notes)


def test_project_bullets_in_the_draft_cover_project_highlights() -> None:
    profile = _profile(
        ["负责订单服务拆分"],
        projects=[
            ProfileProject(id="p1", name="交易中台重构", highlights=["设计跨服务补偿事务方案"])
        ],
    )
    report = audit_coverage(
        _sections(
            ["主导订单服务拆分"],
            projects=[
                {
                    "name": "交易中台重构",
                    "bullets": ["设计跨服务补偿事务方案，保证最终一致"],
                }
            ],
        ),
        profile,
    )
    assert report.projects_missing is False
    assert report.dropped == []


def test_a_project_summarised_into_its_description_is_not_a_drop() -> None:
    """`description` carries content; matching only bullets would false-positive."""
    profile = _profile(
        ["负责订单服务拆分"],
        projects=[
            ProfileProject(id="p1", name="交易中台重构", description="重构交易中台的清结算模块")
        ],
    )
    report = audit_coverage(
        _sections(
            ["主导订单服务拆分"],
            projects=[
                {
                    "name": "交易中台重构",
                    "description": "重构交易中台的清结算模块",
                    "bullets": [],
                }
            ],
        ),
        profile,
    )
    assert report.dropped == []


def test_a_label_length_highlight_is_not_reported_as_dropped() -> None:
    """`优化流程` is too short for overlap to mean anything; flagging it wastes attention."""
    profile = _profile(["优化流程"])
    report = audit_coverage(_sections(["推动研发流程标准化，评审周期缩短一半"]), profile)
    assert report.dropped == []
    assert report.covered == 1


def test_a_bilingual_draft_is_audited_on_its_chinese_track() -> None:
    profile = _profile(["主导订单服务拆分，发布耗时从 40 分钟降到 6 分钟"])
    zh = _sections(["主导订单服务从单体拆分为微服务，发布耗时从 40 分钟降到 6 分钟"])
    report = audit_coverage(
        {"track": "bilingual", "zh_sections": zh, "en_sections": {}}, profile
    )
    assert report.dropped == []
    assert report.draft_bullets == 1


def test_no_profile_means_no_claim_about_coverage() -> None:
    report = audit_coverage(_sections(["主导订单服务拆分"]), None)
    assert report.source_highlights == 0
    assert report.ratio == 1.0
    assert report.notes == []


def test_a_fact_folded_into_the_scope_line_is_not_reported_as_dropped() -> None:
    """The scope line is part of the document, so content moved there is not lost.

    This was a false positive with a real cost: the writer is *told* to lift team size
    and ownership into the role's opener (先总后分) rather than spend a lead bullet on
    it, and the audit then reported the user's own instruction as missing content.
    """
    profile = _profile(["带 8 人后端团队，负责订单与结算两条主链路"])
    sections = {
        "experience_blocks": [
            {
                "company": "字节跳动",
                "title": "后端工程师",
                "scope_line": "带 8 人后端团队，负责订单与结算两条主链路",
                "bullets": ["把支付链路 P99 从 800ms 降到 220ms"],
            }
        ],
        "project_blocks": [],
    }
    report = audit_coverage(sections, profile)
    assert report.dropped == []
    assert report.covered == 1


def test_a_fact_carried_by_the_summary_counts_as_covered() -> None:
    """A headline number legitimately lives in the summary rather than in a bullet."""
    profile = _profile(["主导配置中心建设，覆盖 120 多个服务的配置下发"])
    sections = _sections(["负责服务治理相关工作"])
    sections["summary"] = "后端工程师，主导配置中心建设，覆盖 120 多个服务的配置下发"
    report = audit_coverage(sections, profile)
    assert report.dropped == []


def test_the_dropped_note_quotes_on_a_phrase_boundary() -> None:
    """A mid-word cut reads as a rendering bug, and the user stops trusting the panel."""
    long_highlight = (
        "为了提升打车业务的 GMV 以及满足高质量用户增长的目标，"
        "重构了派单链路的核心调度模型"
    )
    profile = _profile([long_highlight])
    report = audit_coverage(_sections(["负责数据报表开发与维护"]), profile)
    assert report.dropped
    note = " ".join(report.notes)
    # The excerpt is quoted and elided, not sliced at a fixed character count.
    assert "…" in note
    assert "满足高质量用」" not in note


def test_the_dropped_note_states_both_branches_of_the_decision() -> None:
    """Dropping a duplicate is legitimate, so the note may not read as an error.


    Without this the user treats every coverage notice as a defect and regenerates
    repeatedly, which cannot fix a drop that was correct in the first place.
    """
    profile = _profile(["主导配置中心建设，覆盖 120 多个服务的配置下发"])
    report = audit_coverage(_sections(["负责数据报表开发与维护"]), profile)
    note = " ".join(report.notes)
    assert "同一件事" in note
    # The user's own count, not ours: how many of their experiences are missing.
    assert "这 1 条经历" in note
