"""Addition-side audit: does the draft assert anything the profile never said?

These tests pin the *decisions* in `writing_invariants`, not its wording. Each one names
the failure it prevents, because every threshold and exemption in that module exists
because the naive version produced a false positive on correct writing.
"""

from jc.schemas.profile_payload import (
    EvidenceAnswer,
    ProfileExperience,
    ProfilePayload,
    ProfileProject,
)
from jc.services.writing_invariants import audit_additions


def _profile(
    highlights: list[str],
    *,
    summary: str | None = None,
    projects: list[ProfileProject] | None = None,
    answers: list[EvidenceAnswer] | None = None,
) -> ProfilePayload:
    return ProfilePayload(
        summary=summary,
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
        evidence_answers=answers or [],
    )


def _sections(bullets: list[str]) -> dict:
    return {"experience_blocks": [{"company": "字节跳动", "bullets": bullets}]}


def test_an_honest_rewrite_reports_nothing() -> None:
    """The baseline that matters: doing the job correctly must produce a clean audit.

    If rewriting triggers findings, every real run is noise and the audit gets ignored.
    """
    profile = _profile(["参与订单服务拆分，拆成微服务"])
    audit = audit_additions(_sections(["参与订单服务拆分，将单体拆为微服务"]), profile)
    assert audit.holds
    assert audit.findings == []


def test_an_invented_metric_is_a_fabrication() -> None:
    profile = _profile(["负责订单服务拆分，拆成微服务"])
    audit = audit_additions(
        _sections(["负责订单服务拆分为微服务，发布耗时下降 70%"]), profile
    )
    assert not audit.holds
    assert [f.kind for f in audit.fabrications] == ["unsupported_number"]
    assert "70%" in audit.fabrications[0].detail


def test_rewriting_internet_slang_wan_to_the_character_is_not_a_fabrication() -> None:
    """`100w` is Chinese internet shorthand for `100万`, not a different number.

    A real resume evaluated against this module reported `100万` as unsupported because
    the profile only ever said `100w` — same value, different spelling. That false
    positive, not a real fabrication, is what this test pins.
    """
    profile = _profile(["该业务也实现了GMV 100w的既定年度目标"])
    audit = audit_additions(
        _sections(["业务达成年度GMV 100万目标"]), profile
    )
    assert audit.holds
    assert audit.findings == []


def test_rewriting_compound_kw_to_the_character_is_not_a_fabrication() -> None:
    """`4kw` (4 thousand-wan) is `4000万`, not an invented scope figure.

    Same false positive as the `100w` case above, but through the compound suffix: the
    metric regex's unit alternatives are single letters, so `4kw` was captured as `4k`
    with the trailing `w` stranded outside any token, and `4000万` in the rewrite had
    nothing to match against.
    """
    profile = _profile(["全量推送（4kw）到达率达到了55%"])
    audit = audit_additions(
        _sections(["4000万规模的全量推送到达率达到55%以上"]), profile
    )
    assert audit.holds
    assert audit.findings == []


def test_an_acronym_metric_adjacent_to_a_cjk_character_is_recognised() -> None:
    """`GMV` directly preceded by a Chinese character must still match as a term.

    Python's Unicode-aware `\b` treats CJK ideographs as word characters, so `了GMV`
    has no boundary between `了` and `G` and the acronym branch of `_METRIC_RE` used to
    fail silently — `GMV` from the source never entered `corpus_metrics`, so the
    rewritten draft's `GMV` was reported as unsupported even though the source stated
    it verbatim.
    """
    profile = _profile(["该业务也实现了GMV 100w的既定年度目标"])
    audit = audit_additions(_sections(["达成年度 GMV 100 万目标"]), profile)
    assert audit.holds
    assert audit.findings == []


def test_an_invented_scope_count_is_caught_even_without_a_percent_sign() -> None:
    """`6 个业务线` is the most common exaggeration and has no `%` to detect it by."""
    profile = _profile(["负责订单服务拆分，拆成微服务"])
    audit = audit_additions(_sections(["负责订单服务拆分，覆盖 6 条业务线"]), profile)
    assert [f.kind for f in audit.fabrications] == ["unsupported_number"]


def test_a_number_stated_elsewhere_in_the_profile_is_supported() -> None:
    """The writer is told to surface evidence buried in another field. That is correct
    behaviour, so checking a bullet only against its own source line is too narrow."""
    profile = _profile(
        ["负责订单服务拆分，拆成微服务"],
        summary="5 年后端经验，主导的订单链路日均 1200 万单",
    )
    audit = audit_additions(
        _sections(["负责订单服务拆分，支撑日均 1200 万单的订单链路"]), profile
    )
    assert audit.holds


def test_a_number_the_user_typed_as_evidence_is_supported() -> None:
    """`evidence_answers` are user-authored facts, not model output."""
    profile = _profile(
        ["负责推送链路改造"],
        answers=[
            EvidenceAnswer(
                field_path="experiences[0].highlights[0]",
                question="改造后推送成功率变化？",
                answer="成功率从 92% 提升到 99.5%",
            )
        ],
    )
    audit = audit_additions(
        _sections(["负责推送链路改造，成功率从 92% 提升到 99.5%"]), profile
    )
    assert audit.holds


def test_calendar_years_are_not_treated_as_claims() -> None:
    """A date range rendered into a bullet is structural, not a metric."""
    profile = _profile(["负责订单服务拆分"])
    audit = audit_additions(_sections(["负责订单服务拆分（2021 年立项）"]), profile)
    assert audit.holds


def test_a_bare_ordinal_is_not_a_claim() -> None:
    profile = _profile(["负责订单服务拆分，分两期上线"])
    audit = audit_additions(_sections(["负责订单服务拆分，第 2 期完成灰度"]), profile)
    assert audit.holds


def test_upgrading_participation_to_ownership_is_a_fabrication() -> None:
    """The damage this prevents is specific: it passes the screen and collapses in the
    interview, and the cost lands entirely on the user."""
    profile = _profile(["参与统一配置中心建设，负责客户端 SDK 部分"])
    audit = audit_additions(
        _sections(["主导统一配置中心建设，负责客户端 SDK 部分"]), profile
    )
    assert [f.kind for f in audit.fabrications] == ["ownership_upgrade"]


def test_ownership_already_in_the_source_is_not_an_upgrade() -> None:
    profile = _profile(["主导统一配置中心建设"])
    audit = audit_additions(_sections(["主导统一配置中心建设，覆盖客户端 SDK"]), profile)
    assert audit.holds


def test_ownership_stated_next_to_the_line_is_not_an_upgrade() -> None:
    """A project whose `role` says 负责人 establishes ownership for its highlights.
    Reading only the matched line would report the writer for using the profile."""
    profile = _profile(
        ["日常工作"],
        projects=[
            ProfileProject(
                id="p1",
                name="统一配置中心",
                role="技术负责人，主导方案设计",
                highlights=["参与配置推送链路的设计与落地"],
            )
        ],
    )
    audit = audit_additions(
        {
            "project_blocks": [
                {"name": "统一配置中心", "bullets": ["主导配置推送链路的设计与落地"]}
            ]
        },
        profile,
    )
    assert audit.holds


def test_a_bullet_with_no_recognisable_source_is_reported_but_not_a_fabrication() -> None:
    """Merging two highlights that describe the same work is legitimate, and it breaks
    attribution. So this is evidence for a reader, never a verdict."""
    profile = _profile(["负责订单服务拆分", "搭建全链路压测平台"])
    audit = audit_additions(_sections(["推动基础架构治理专项落地"]), profile)
    kinds = [f.kind for f in audit.findings]
    assert "unattributed_bullet" in kinds
    assert audit.holds


def test_an_english_term_absent_from_the_profile_is_attention_not_fabrication() -> None:
    """An English rendering of a Chinese term is indistinguishable from a new skill
    claim without a model, so the audit reports it and lets a human decide."""
    profile = _profile(["负责服务监控埋点体系建设"])
    audit = audit_additions(
        _sections(["负责服务可观测性体系建设，覆盖 Prometheus 指标采集"]), profile
    )
    assert audit.holds
    assert [f.kind for f in audit.findings if f.severity == "attention"] == [
        "unsupported_term"
    ]


def test_bilingual_drafts_are_audited_on_the_chinese_track_only() -> None:
    """Auditing both tracks double-counts every finding; the metric is calibrated on zh."""
    profile = _profile(["负责订单服务拆分，拆成微服务"])
    sections = {
        "track": "bilingual",
        "zh_sections": _sections(["负责订单服务拆分，发布耗时下降 70%"]),
        "en_sections": _sections(["Owned order service split, cut release time by 70%"]),
    }
    audit = audit_additions(sections, profile)
    assert len(audit.fabrications) == 1


def test_a_missing_profile_does_not_invent_findings() -> None:
    """Called before confirmation, the audit has nothing to compare against and must
    stay silent rather than report the whole draft as fabricated."""
    audit = audit_additions(_sections(["负责订单服务拆分，下降 70%"]), None)
    assert audit.holds
    assert audit.draft_bullets == 1
    assert audit.attributed_bullets == 0
