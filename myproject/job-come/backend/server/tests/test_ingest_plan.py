"""Pure routing policy plus real local PDF inspection (no model/network)."""

import io

import pytest

from jc.services.document_extractor import DocumentExtractor
from jc.services.ingest_plan import IngestRoute, select_ingest_plan, usable_text

TEXT = (
    "Software engineer building reliable services, order processing and distributed systems. " * 3
)


@pytest.mark.parametrize("kind", ["pdf", "docx", "txt"])
def test_native_text_selects_text_even_if_document_contains_portrait(kind):
    assert select_ingest_plan(kind, TEXT).route == IngestRoute.TEXT


def test_sparse_profile_is_not_routing_evidence():
    assert select_ingest_plan("pdf", TEXT).route == IngestRoute.TEXT
    assert select_ingest_plan("pdf", TEXT, scanned_pages=True).route == IngestRoute.PDF_VISION
    assert not usable_text("\ufffd" * 30 + "x" * 50)


def pdf_with_image(*, scanned=False, mixed=False):
    fitz = pytest.importorskip("fitz")
    image = pytest.importorskip("PIL.Image")
    png = io.BytesIO()
    image.new("RGB", (100, 100), "white").save(png, format="PNG")
    with fitz.open() as doc:
        page = doc.new_page()
        if not scanned:
            page.insert_textbox(fitz.Rect(30, 30, 500, 400), TEXT)
        page.insert_image(
            page.rect if scanned else fitz.Rect(480, 40, 540, 100), stream=png.getvalue()
        )
        if mixed:
            page = doc.new_page()
            page.insert_image(page.rect, stream=png.getvalue())
        return doc.tobytes()


@pytest.mark.parametrize(
    "scanned,mixed,expected", [(False, False, False), (True, False, True), (False, True, True)]
)
def test_real_pdf_distinguishes_portrait_from_scan(scanned, mixed, expected):
    assert (
        DocumentExtractor().has_scanned_pdf_pages(pdf_with_image(scanned=scanned, mixed=mixed))
        == expected
    )


def test_vision_refuses_silent_page_truncation():
    fitz = pytest.importorskip("fitz")
    with fitz.open() as doc:
        for _ in range(6):
            doc.new_page()
        raw = doc.tobytes()
    with pytest.raises(ValueError, match="pdf_vision_page_limit"):
        DocumentExtractor.pdf_page_images_from_bytes(raw, require_all_pages=True)
