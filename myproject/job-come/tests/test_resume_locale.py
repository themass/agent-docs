"""Locale ↔ template mapping and English HTML track."""

from jobcome.resume_locale import detect_source_locale, normalize_locale, normalize_track, template_id_for_locale
from jobcome.services.profile_i18n import overlay_profile
from jobcome.services.resume_draft_builder import ResumeDraftBuilder
from jobcome.services.resume_render_engine import ResumeRenderEngine
from jobcome.services.resume_service import compose_bilingual_sections
from jobcome.schemas.profile_payload import (
    ProfileContact,
    ProfileExperience,
    ProfileI18nExperience,
    ProfileI18nPack,
    ProfilePayload,
)


def test_locale_maps_to_template() -> None:
    from jobcome.resume_locale import needs_i18n_prepare

    assert template_id_for_locale("zh-CN") == "zh-one-page"
    assert template_id_for_locale("en") == "en-two-page"
    assert template_id_for_locale("zh-en") == "zh-en-bilingual"
    assert normalize_locale("en-US") == "en-US"
    assert normalize_track("bilingual") == "zh-en"
    assert needs_i18n_prepare("zh-CN") is False
    assert needs_i18n_prepare("en-US") is True
    assert needs_i18n_prepare("zh-en") is True


def test_detect_source_locale_cjk_vs_english() -> None:
    assert detect_source_locale("高级后端工程师，主导订单服务重构") == "zh-CN"
    assert detect_source_locale("Senior backend engineer. Built order services.") == "en-US"


def test_overlay_keeps_experience_ids() -> None:
    profile = ProfilePayload(
        contact=ProfileContact(name="张三"),
        summary="中文总结",
        experiences=[
            ProfileExperience(
                id="exp1",
                company="某互联网公司",
                title="工程师",
                start_date="2020-01",
                highlights=["参与订单系统"],
            )
        ],
        i18n={
            "en-US": ProfileI18nPack(
                summary="English summary",
                experiences=[
                    ProfileI18nExperience(
                        id="exp1",
                        title="Software Engineer",
                        highlights=["Shipped the order service"],
                    )
                ],
            )
        },
    )
    overlaid = overlay_profile(profile, "en-US")
    assert overlaid.experiences[0].id == "exp1"
    assert overlaid.experiences[0].company == "某互联网公司"
    assert overlaid.experiences[0].title == "Software Engineer"
    assert overlaid.summary == "English summary"


def test_english_draft_uses_english_labels() -> None:
    profile = ProfilePayload(
        contact=ProfileContact(name="Li Si", email="lisi@example.com"),
        summary="Full-stack engineer.",
        experiences=[
            ProfileExperience(
                id="exp1",
                company="Example Corp",
                title="Software Engineer",
                start_date="2019-06",
                end_date=None,
                highlights=["Built dashboards"],
            )
        ],
    )
    sections, _ = ResumeDraftBuilder().build(profile, elevation_level="conservative", locale="en-US")
    assert sections["skills_block"]["title"] == "Skills"
    assert "Present" in sections["experience_blocks"][0]["date_range"]
    html = ResumeRenderEngine().render_html(sections, template_id="en-two-page")
    assert "Summary" in html
    assert "Experience" in html
    assert "Li Si" in html


def test_bilingual_html_contains_both_summaries() -> None:
    zh = {
        "header": {"name": "张三", "headline": "后端工程师", "contact_line": "a@b.com"},
        "summary": "五年后端经验。",
        "experience_blocks": [
            {
                "company": "某公司",
                "title": "工程师",
                "date_range": "2020 – 至今",
                "bullets": ["重构订单服务"],
            }
        ],
        "education_blocks": [],
        "skills_block": {"title": "技能", "content": "Python"},
    }
    en = {
        "header": {"name": "Zhang San", "headline": "Backend Engineer", "contact_line": "a@b.com"},
        "summary": "Five years of backend experience.",
        "experience_blocks": [
            {
                "company": "某公司",
                "title": "Engineer",
                "date_range": "2020 – Present",
                "bullets": ["Rebuilt the order service"],
            }
        ],
        "education_blocks": [],
        "skills_block": {"title": "Skills", "content": "Python"},
    }
    sections = compose_bilingual_sections(zh, en, zh_draft_id="zh1", en_draft_id="en1")
    html = ResumeRenderEngine().render_html(sections, template_id="zh-en-bilingual")
    assert "个人总结" in html
    assert "Summary" in html
    assert "五年后端经验" in html
    assert "Five years of backend experience" in html
    assert "page-break" in html
