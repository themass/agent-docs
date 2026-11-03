"""Free-tier exports carry a sparse attribution; member exports and previews do not."""

from __future__ import annotations

import io

from docx import Document

from jc.services.resume_render_engine import WATERMARK_TEXT, ResumeRenderEngine
from test_export_lifecycle import FIXTURE_SECTIONS


def test_html_without_the_flag_has_no_watermark():
    html = ResumeRenderEngine().render_html(FIXTURE_SECTIONS, template_id="zh-one-page")
    assert "jc-watermark" not in html


def test_html_with_the_flag_carries_a_few_sparse_marks_before_body_close():
    html = ResumeRenderEngine().render_html(
        FIXTURE_SECTIONS, template_id="zh-one-page", watermark=True
    )
    assert html.count(WATERMARK_TEXT) == 3, "a few lines, not a wall of text"
    assert html.index("jc-watermark") < html.lower().rindex("</body>")


def test_docx_with_the_flag_stamps_the_header_only():
    engine = ResumeRenderEngine()
    plain = Document(io.BytesIO(engine.render_docx(FIXTURE_SECTIONS)))
    marked = Document(io.BytesIO(engine.render_docx(FIXTURE_SECTIONS, watermark=True)))
    assert WATERMARK_TEXT not in "\n".join(p.text for p in plain.sections[0].header.paragraphs)
    assert WATERMARK_TEXT in "\n".join(p.text for p in marked.sections[0].header.paragraphs)
    # The body is the same document either way.
    assert _body(plain) == _body(marked)


def _body(document) -> list[str]:
    return [p.text for p in document.paragraphs]
