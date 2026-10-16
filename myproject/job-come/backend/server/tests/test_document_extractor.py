"""Document extraction routes for resume ingest."""

from __future__ import annotations

import io
import zipfile

from jc.services.document_extractor import DocumentExtractor


def test_classify_txt_and_image() -> None:
    ex = DocumentExtractor()
    assert ex.classify("cv.txt", "text/plain") == "txt"
    assert ex.classify("photo.jpg", "image/jpeg") == "image"


def test_extract_plain_txt() -> None:
    ex = DocumentExtractor()
    text = ex.extract(file_name="cv.txt", content_type="text/plain", raw_bytes=b"name: Alice\n")
    assert "Alice" in text


def test_docx_embedded_images_reads_media() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")
        zf.writestr("word/media/img1.png", b"\x89PNG\r\n\x1a\n")
    ex = DocumentExtractor()
    images = ex.docx_embedded_images(buf.getvalue())
    assert len(images) == 1
    assert images[0][1] == "image/png"
