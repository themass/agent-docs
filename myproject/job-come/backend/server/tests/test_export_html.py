"""HTML export artifact and shared-template contract."""

import pytest

from jc.services.export_quality import validate_export
from jc.services.resume_render_engine import ResumeRenderEngine
from test_export_pdf import FIXTURE_SECTIONS

TEMPLATES = ["zh-one-page", "en-two-page"]


@pytest.mark.parametrize("template_id", TEMPLATES)
def test_html_export_is_self_contained(template_id):
    """A downloaded .html must render offline and carry no executable payload."""
    html = ResumeRenderEngine().render_html(FIXTURE_SECTIONS, template_id=template_id)

    assert "<style>" in html, "styles must be inlined, not linked"
    assert "<link" not in html.lower()
    assert "<script" not in html.lower()
    assert "@import" not in html
    # No remote asset of any kind, so the file works from mail or disk.
    assert "http://" not in html and "https://" not in html


@pytest.mark.parametrize("template_id", TEMPLATES)
def test_html_export_passes_quality_gate(template_id):
    html = ResumeRenderEngine().render_html(FIXTURE_SECTIONS, template_id=template_id)
    quality = validate_export(html.encode("utf-8"), "html", FIXTURE_SECTIONS)
    assert quality["text_retention"] == 1.0
    assert quality["format"] == "html"


def test_html_quality_rejects_linked_assets():
    markup = '<html><head><link rel="stylesheet" href="x.css"></head><body>张三</body></html>'
    with pytest.raises(ValueError, match="self-contained"):
        validate_export(markup.encode("utf-8"), "html", FIXTURE_SECTIONS)


def test_html_quality_rejects_scripts():
    markup = "<html><body>张三<script>alert(1)</script></body></html>"
    with pytest.raises(ValueError, match="self-contained"):
        validate_export(markup.encode("utf-8"), "html", FIXTURE_SECTIONS)


def test_html_quality_rejects_missing_content():
    markup = "<html><body><p>完全不同的人</p></body></html>"
    with pytest.raises(ValueError, match="missing"):
        validate_export(markup.encode("utf-8"), "html", FIXTURE_SECTIONS)


def test_html_quality_rejects_non_document():
    with pytest.raises(ValueError, match="document root"):
        validate_export(b"just text", "html", FIXTURE_SECTIONS)


@pytest.mark.parametrize("template_id", TEMPLATES)
def test_templates_use_semantic_ats_safe_markup(template_id):
    """ATS parsers rely on real headings and lists, and on bullet text not living in CSS."""
    html = ResumeRenderEngine().render_html(FIXTURE_SECTIONS, template_id=template_id)

    assert "<h1" in html and "<h2" in html
    assert "<ul" in html and "<li>" in html
    assert "<table" not in html.lower(), "multi-column tables break ATS extraction"
    # Bullet glyphs are drawn, never injected as text content.
    assert 'content: ""' in html


def test_empty_sections_do_not_emit_headings():
    """An empty section must not leave a dangling heading in the document."""
    sections = dict(FIXTURE_SECTIONS, project_blocks=[], summary="")
    html = ResumeRenderEngine().render_html(sections, template_id="zh-one-page")
    assert "项目经历" not in html
    assert "个人总结" not in html
    assert "工作经历" in html


def test_renderer_controls_section_order_not_the_model():
    """A malformed section_order must not drop or duplicate any section."""
    sections = dict(
        FIXTURE_SECTIONS,
        section_order=["skills", "skills", "bogus_section", "experience"],
    )
    html = ResumeRenderEngine().render_html(sections, template_id="zh-one-page")

    assert html.count("<h2 class=\"section-title\">技能</h2>") == 1
    assert html.count("<h2 class=\"section-title\">工作经历</h2>") == 1
    # Sections omitted from a bad order are still rendered.
    assert "教育背景" in html
    assert "个人总结" in html
    assert "bogus_section" not in html
    # And the order the model did supply is respected: skills before experience.
    assert html.index("技能") < html.index("工作经历")


def test_bilingual_template_keeps_tracks_on_separate_pages():
    sections = {
        "track": "bilingual",
        "zh_sections": FIXTURE_SECTIONS,
        "en_sections": dict(
            FIXTURE_SECTIONS,
            header={**FIXTURE_SECTIONS["header"], "name": "San Zhang"},
        ),
    }
    html = ResumeRenderEngine().render_html(sections, template_id="zh-en-bilingual")

    assert "张三" in html and "San Zhang" in html
    assert html.count('class="track ') == 2
    assert "page-break-before: always" in html


def test_all_templates_share_one_stylesheet():
    """Visual drift between formats comes from duplicated CSS; keep a single source."""
    engine = ResumeRenderEngine()
    marker = "--space-section"
    for template_id in (*TEMPLATES, "zh-en-bilingual"):
        sections = (
            {
                "track": "bilingual",
                "zh_sections": FIXTURE_SECTIONS,
                "en_sections": FIXTURE_SECTIONS,
            }
            if template_id == "zh-en-bilingual"
            else FIXTURE_SECTIONS
        )
        html = engine.render_html(sections, template_id=template_id)
        assert marker in html, f"{template_id} does not use the shared theme"


@pytest.mark.parametrize("template_id", TEMPLATES)
def test_project_bullets_survive_into_the_exported_document(template_id):
    """项目经历 must render with every bullet, not collapse to a title.

    Projects used to be dropped before rendering, and later carried only a single free-text
    description, so a senior profile exported a document far thinner than the career behind it.
    """
    html = ResumeRenderEngine().render_html(FIXTURE_SECTIONS, template_id=template_id)

    assert "统一配置中心" in html
    assert "120+ 服务" in html
    assert "事故下降 70%" in html
    assert "面向全集团的配置下发平台" in html
    assert "2021-03 – 2023-08" in html


def test_project_section_renders_before_education_and_skills():
    """Projects are senior-signal content; burying them under 技能 wastes the strongest evidence."""
    html = ResumeRenderEngine().render_html(FIXTURE_SECTIONS, template_id="zh-one-page")

    assert html.index("项目经历") < html.index("教育背景")
    assert html.index("项目经历") < html.index("统一配置中心") + len(html)
    assert html.index("工作经历") < html.index("项目经历")


def _sections(scope: str | None) -> dict:
    return {
        "locale": "zh-CN",
        "header": {"name": "李国庆", "headline": "AI研发工程师", "contact_line": "a@b.com"},
        "summary": "",
        "experience_blocks": [
            {
                "company": "快手",
                "title": "风控/审核系统组/服务端leader",
                "date_range": "2021-07 – 2024-02",
                "scope_line": scope,
                "bullets": ["负责风控团队审核方向的后端团队管理与架构演进"],
            }
        ],
        "education_blocks": [],
        "project_blocks": [],
        "skills_block": {"title": "技能", "content": "java"},
    }


def test_a_short_scope_rides_the_title_row_instead_of_taking_its_own_line():
    """"带10人团队" is role metadata, not a one-phrase paragraph.

    On its own line it read as an orphan bullet and cost a full line per entry.
    """
    html = ResumeRenderEngine().render_html(_sections("带10人团队"), template_id="zh-one-page")
    head = html[html.index('class="entry-head"') : html.index("<ul")]
    assert "带10人团队" in head
    assert 'class="entry-scope"' not in html
    assert 'class="entry-scope-inline"' in html


def test_a_full_scope_sentence_keeps_its_own_lead_paragraph():
    scope = "带 10 人团队，支撑视频、直播、评论与电商的内容安全审核，服务 5000+ 审核人员"
    html = ResumeRenderEngine().render_html(_sections(scope), template_id="zh-one-page")
    assert 'class="entry-scope"' in html
    assert 'class="entry-scope-inline"' not in html
    head = html[html.index('class="entry-head"') : html.index('class="entry-scope"')]
    assert scope not in head


def test_the_word_export_applies_the_same_scope_rule():
    """DOCX goes to the same recruiters; the two formats must not disagree."""
    from docx import Document
    import io

    short = Document(io.BytesIO(ResumeRenderEngine().render_docx(_sections("带10人团队"))))
    texts = [p.text for p in short.paragraphs]
    assert any("风控/审核系统组/服务端leader · 带10人团队" in t for t in texts)
    assert "带10人团队" not in [t.strip() for t in texts]

    sentence = "带 10 人团队，支撑视频、直播、评论与电商的内容安全审核，服务 5000+ 审核人员"
    long = Document(io.BytesIO(ResumeRenderEngine().render_docx(_sections(sentence))))
    long_texts = [p.text.strip() for p in long.paragraphs]
    assert sentence in long_texts
