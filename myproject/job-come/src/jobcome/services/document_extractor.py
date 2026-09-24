"""Extract plain text / markdown from uploaded resume files."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class DocumentExtractor:
    def extract(self, *, file_name: str, content_type: str | None, raw_bytes: bytes) -> str:
        ext = Path(file_name).suffix.lower()
        if ext == ".pdf" or (content_type or "").endswith("pdf"):
            return self._extract_pdf(raw_bytes)
        if ext == ".docx":
            return self._extract_docx(raw_bytes)
        if ext in {".doc"}:
            return ""
        if ext in {".png", ".jpg", ".jpeg", ".webp"} or (content_type or "").startswith("image/"):
            return ""
        return raw_bytes.decode("utf-8", errors="ignore")[:50_000]

    @staticmethod
    def pdf_page_images(raw_bytes: bytes, *, max_pages: int = 3, scale: float = 2.0) -> list[tuple[bytes, str]]:
        """Render PDF pages to PNG bytes for vision OCR."""
        try:
            import fitz  # pymupdf
        except ImportError:
            return []

        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        images: list[tuple[bytes, str]] = []
        try:
            matrix = fitz.Matrix(scale, scale)
            for idx, page in enumerate(doc):
                if idx >= max_pages:
                    break
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                images.append((pix.tobytes("png"), "image/png"))
        finally:
            doc.close()
        return images

    @staticmethod
    def _extract_pdf(raw_bytes: bytes) -> str:
        try:
            import fitz  # pymupdf
        except ImportError:
            return ""
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        try:
            parts: list[str] = []
            for page in doc:
                text = page.get_text("text", sort=True).strip()
                if text:
                    parts.append(text)
            return "\n\n".join(parts)
        finally:
            doc.close()

    @staticmethod
    def _extract_docx(raw_bytes: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            xml = zf.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for para in root.findall(".//w:p", ns):
            texts = [node.text for node in para.findall(".//w:t", ns) if node.text]
            if texts:
                paragraphs.append("".join(texts))
        return "\n".join(paragraphs)

    @staticmethod
    def is_probably_scanned(text: str, *, file_name: str) -> bool:
        ext = Path(file_name).suffix.lower()
        if ext in {".png", ".jpg", ".jpeg", ".webp"}:
            return True
        cleaned = re.sub(r"\s+", "", text)
        # Chinese resumes often have thin text layers; treat short extract as scanned.
        if len(cleaned) < 120:
            return True
        return False

    @staticmethod
    def is_pdf(file_name: str, content_type: str | None) -> bool:
        ext = Path(file_name).suffix.lower()
        return ext == ".pdf" or (content_type or "").endswith("pdf")
