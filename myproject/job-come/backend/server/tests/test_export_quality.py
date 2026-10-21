from unittest.mock import AsyncMock

import pytest

from jc.services.resume_render_engine import ResumeRenderEngine
from test_export_pdf import FIXTURE_SECTIONS


def test_docx_preserves_all_sections():
    from jc.services.export_quality import validate_export

    sections = dict(
        FIXTURE_SECTIONS,
        project_blocks=[
            {
                "name": "Checkout Migration",
                "description": "Migrated checkout to new API",
                "bullets": ["Zero downtime deployment"],
            }
        ],
    )
    content = ResumeRenderEngine().render_docx(sections)
    quality = validate_export(content, "docx", sections)
    assert quality["text_retention"] == 1.0


def test_invalid_pdf_rejected():
    from jc.services.export_quality import validate_export

    with pytest.raises(ValueError):
        validate_export(b"<html>not pdf</html>", "pdf", FIXTURE_SECTIONS)


def test_pdf_missing_content_rejected():
    import fitz

    from jc.services.export_quality import validate_export

    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 50), "Wrong person")
        with pytest.raises(ValueError, match="content"):
            validate_export(doc.tobytes(), "pdf", FIXTURE_SECTIONS)


@pytest.mark.parametrize(
    "template,track",
    [("zh-one-page", "zh-CN"), ("en-two-page", "en-US"), ("zh-en-bilingual", "bilingual")],
)
def test_actual_pdf_quality_all_templates(template, track):
    from jc.services.export_quality import validate_export

    sections = dict(
        FIXTURE_SECTIONS,
        locale=track,
        project_blocks=[
            {
                "name": "Migration",
                "date_range": "2025",
                "description": "New checkout API",
                "bullets": ["No downtime"],
            }
        ],
    )
    if track == "bilingual":
        sections = {"track": "bilingual", "zh_sections": sections, "en_sections": sections}
    renderer = ResumeRenderEngine()
    result = validate_export(
        renderer.render_pdf(renderer.render_html(sections, template_id=template)), "pdf", sections
    )
    assert result["text_retention"] == 1.0
    assert result["pages"] <= (2 if track == "bilingual" else 1)


@pytest.mark.asyncio
async def test_cross_profile_draft_is_rejected():
    from types import SimpleNamespace

    from jc.exceptions import NotFoundError
    from jc.schemas.resume import ExportRequest
    from jc.services.resume_service import ResumeService

    service = object.__new__(ResumeService)
    service._profiles = SimpleNamespace(get=AsyncMock())
    service._resumes = SimpleNamespace(
        get_draft_by_id=AsyncMock(return_value=SimpleNamespace(profile_id="other"))
    )
    with pytest.raises(NotFoundError):
        await service.export(
            "own", actor=SimpleNamespace(user_id="user"), body=ExportRequest(draft_id="foreign")
        )


# Export lifecycle (including real PDF failure and all persisted reviewer states)
# is covered by test_export_lifecycle using real SQL sessions instead of mocks
# that cannot model ORM expiration, rollback or a broken transaction.


def test_word_declares_cjk_fonts_and_a4():
    import io

    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(io.BytesIO(ResumeRenderEngine().render_docx(FIXTURE_SECTIONS)))
    for name in ["Normal", "Title", "Heading 1", "Heading 2", "List Bullet"]:
        assert doc.styles[name].element.rPr.rFonts.get(qn("w:eastAsia")) == "Heiti SC"
    assert round(doc.sections[0].page_width.cm, 1) == 21.0
