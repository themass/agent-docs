"""Offline PDF text-layer diagnostics, not a promise to pass an employer's ATS."""

import pytest

from jc.services.export_quality import validate_export
from jc.services.pdf_text_quality import inspect_pdf_text, normalize_extracted_text


def test_comparison_handles_typography_without_changing_numbers():
    assert normalize_extracted_text("Gene\u0300ve Master’s 2020–2024") == (
        normalize_extracted_text("Genève Master's 2020-2024")
    )
    assert normalize_extracted_text("-30%") != normalize_extracted_text("30%")
    assert normalize_extracted_text("10") != normalize_extracted_text("100")


def test_diagnostics_never_contain_candidate_text_and_do_not_claim_ats_pass():
    report = inspect_pdf_text("private@example.com \ufffd \ue001", {"header": {}})
    assert report["status"] == "warning"
    assert {item["code"] for item in report["warnings"]} == {
        "replacement_character",
        "private_use_character",
    }
    assert "private@example.com" not in str(report)
    assert "score" not in report


def test_contact_absence_is_not_invented_and_date_risk_is_advisory():
    report = inspect_pdf_text("张三 2020–2024 Python", {"header": {"name": "张三"}})
    assert report["checks"]["contact_text"] == "not_applicable"
    assert any(w["code"] == "non_ascii_date_separator" for w in report["warnings"])


def test_pdf_contacts_and_unicode_dates_remain_extractable():
    import fitz

    sections = {
        "header": {"name": "Jane", "contact_line": "jane@example.com"},
        "experience_blocks": [{"company": "Acme", "date_range": "2020-2024"}],
    }
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_htmlbox(
            fitz.Rect(50, 50, 550, 150), "Jane jane@example.com Acme 2020\u20132024"
        )
        quality = validate_export(doc.tobytes(), "pdf", sections)
    assert quality["text_retention"] == 1.0
    assert quality["text_layer"]["checks"]["contact_text"] == "present"


def test_missing_contacts_still_block_export():
    import fitz

    with fitz.open() as doc:
        doc.new_page().insert_text((50, 50), "Jane")
        with pytest.raises(ValueError, match="missing"):
            validate_export(
                doc.tobytes(),
                "pdf",
                {
                    "header": {"name": "Jane", "contact_line": "jane@example.com"},
                },
            )


@pytest.mark.parametrize(
    "template,locale",
    [("zh-one-page", "zh-CN"), ("en-two-page", "en-US"), ("zh-en-bilingual", "bilingual")],
)
def test_real_template_text_layer_preserves_cjk_contacts_and_entry_order(template, locale):
    import fitz

    from jc.services.resume_render_engine import ResumeRenderEngine
    from test_export_pdf import FIXTURE_SECTIONS

    source = dict(FIXTURE_SECTIONS, locale=locale)
    sections = (
        {"track": "bilingual", "zh_sections": source, "en_sections": source}
        if locale == "bilingual"
        else source
    )
    renderer = ResumeRenderEngine()
    content = renderer.render_pdf(renderer.render_html(sections, template_id=template))
    report = validate_export(content, "pdf", sections)["text_layer"]
    assert report["checks"]["contact_text"] == "present"
    assert not {w["code"] for w in report["warnings"]} & {
        "replacement_character",
        "private_use_character",
    }
    with fitz.open(stream=content, filetype="pdf") as doc:
        extracted = normalize_extracted_text("\n".join(page.get_text() for page in doc))
    assert "张三" in extracted and "13800138000" in extracted
    # Regression for these templates, not a universal multi-column reading-order guarantee.
    assert extracted.index("某互联网公司") < extracted.index("P99")
    assert extracted.index("统一配置中心") < extracted.index("120+")
