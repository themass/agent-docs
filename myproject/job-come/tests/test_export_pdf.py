"""Resume export regression — HTML always; PDF when Playwright available."""

from __future__ import annotations

import pytest

from jobcome.services.resume_render_engine import ResumeRenderEngine

FIXTURE_SECTIONS = {
    "locale": "zh-CN",
    "header": {
        "name": "张三",
        "headline": "高级后端工程师",
        "contact_line": "zhangsan@example.com · 13800138000",
    },
    "summary": "5年后端开发经验，熟悉 Python、FastAPI、MySQL、Redis。",
    "experience_blocks": [
        {
            "company": "某互联网公司",
            "title": "高级后端工程师",
            "date_range": "2020-01 – 至今",
            "bullets": ["主导订单服务重构，接口 P99 降低 30%"],
        }
    ],
    "education_blocks": [
        {
            "school": "某大学",
            "degree_line": "计算机科学 · 本科",
            "date_range": "2016 – 2020",
        }
    ],
    "skills_block": {"title": "技能", "content": "Python, FastAPI, MySQL, Redis"},
    "project_blocks": [],
    "section_order": ["summary", "experience", "education", "skills", "projects"],
}


def test_export_html_contains_resume_keywords() -> None:
    engine = ResumeRenderEngine()
    html = engine.render_html(FIXTURE_SECTIONS)
    assert "张三" in html
    assert "高级后端工程师" in html
    assert "P99" in html or "订单" in html


def test_export_pdf_page_count_and_text() -> None:
    engine = ResumeRenderEngine()
    html = engine.render_html(FIXTURE_SECTIONS)
    try:
        pdf_bytes = engine.render_pdf(html)
    except RuntimeError as exc:
        pytest.skip(f"playwright unavailable: {exc}")

    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count >= 1
    text = "".join(page.get_text() for page in doc)
    assert "张三" in text
    assert "后端" in text or "Python" in text
