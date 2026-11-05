"""Screening diagnostics: say whether a draft will actually be read."""

from jc.services.resume_diagnostics import diagnose


def _sections(*bullets: str, skills: str = "", summary: str = "") -> dict:
    return {
        "header": {"name": "张三", "headline": "后端工程师", "contact_line": "a@b.com"},
        "summary": summary,
        "experience_blocks": [
            {
                "company": "某公司",
                "title": "后端工程师",
                "date_range": "2020-01 – 至今",
                "bullets": list(bullets),
            }
        ],
        "skills_block": {"title": "技能", "content": skills},
    }


def test_missing_job_keywords_are_reported_without_telling_the_user_to_add_them() -> None:
    """A missing keyword may be a skill the user lacks; adding it would be a lie."""
    result = diagnose(
        _sections("优化订单服务的写入链路，P99 从 420ms 降到 90ms"),
        job_keywords=["可观测性", "Kubernetes"],
    )

    assert result.missing_keywords == ["可观测性", "Kubernetes"]
    note = next(n for n in result.notes if "没出现" in n)
    assert "没做过就不要加" in note


def test_a_keyword_in_a_bullet_counts_as_covered() -> None:
    result = diagnose(
        _sections("搭建可观测性体系，覆盖 40 多个服务"),
        job_keywords=["可观测性"],
    )
    assert result.missing_keywords == []
    assert result.skills_only_keywords == []


def test_a_keyword_only_in_the_skills_line_is_flagged_as_unproven() -> None:
    """Skills-line-only claims are exactly what gets picked apart in interviews."""
    result = diagnose(
        _sections("负责订单服务的日常迭代", skills="Go、Kubernetes、MySQL"),
        job_keywords=["Kubernetes"],
    )
    assert result.skills_only_keywords == ["Kubernetes"]
    assert any("只出现在技能里" in n for n in result.notes)


def test_an_over_long_bullet_is_called_out() -> None:
    result = diagnose(_sections("负责" + "订单链路的治理与优化工作" * 16))
    assert result.longest_bullet_chars > 160
    assert any("一眼读不完" in n for n in result.notes)


def test_a_long_document_warns_about_the_first_page() -> None:
    """Page estimates are calibrated against the real templates, not guessed."""
    bullet = "主导订单服务拆分与容量治理，P99 从 420ms 降到 90ms，支撑日均 1200 万单稳定运行"
    result = diagnose(_sections(*[bullet] * 80))
    assert result.estimated_pages > 2.2
    assert any("第一页" in n for n in result.notes)


def test_a_thin_document_points_back_at_the_evidence_questions() -> None:
    result = diagnose(_sections("负责订单服务"))
    assert result.estimated_pages < 0.6
    assert any("偏薄" in n for n in result.notes)


def test_a_healthy_draft_produces_no_notes() -> None:
    """A well-filled 1.5-page resume is the target shape and must be left alone."""
    bullets = [
        "主导订单服务拆分，P99 从 420ms 降到 90ms，支撑日均 1200 万单稳定运行",
        "搭建可观测性体系，覆盖 40 多个服务，故障定位时长从 35 分钟缩短到 6 分钟",
        "推动数据库分库分表落地，单表写入压力下降 70%，扩容周期从两周缩短到两天",
    ] * 8
    result = diagnose(_sections(*bullets), job_keywords=["可观测性"])
    assert 0.6 <= result.estimated_pages <= 2.2
    assert result.notes == []
    assert result.bullet_count == 24


def test_a_bilingual_draft_is_measured_on_its_chinese_track() -> None:
    zh = _sections("搭建可观测性体系，覆盖 40 多个服务")
    result = diagnose(
        {"track": "bilingual", "zh_sections": zh, "en_sections": {}},
        job_keywords=["可观测性"],
    )
    assert result.missing_keywords == []
    assert result.bullet_count == 1


def test_duplicate_and_single_character_keywords_are_ignored() -> None:
    result = diagnose(
        _sections("负责订单服务"),
        job_keywords=["Go", "Go", "go", "C", " "],
    )
    assert [h.keyword for h in result.keyword_hits] == ["Go"]
