"""Extract plain text and visual assets from uploaded resume files."""

from __future__ import annotations

import asyncio
import io
import logging
import mimetypes
import re
import zipfile
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

ResumeFileKind = Literal["pdf", "docx", "doc", "txt", "image", "unknown"]

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_DOCX_MEDIA_SUFFIXES = _IMAGE_EXTENSIONS | {".emf", ".wmf"}
logger = logging.getLogger(__name__)


class DocumentExtractor:
    # Vision limits — balance cost vs multi-page / embedded-image resumes
    PDF_VISION_MAX_PAGES = 5
    DOCX_VISION_MAX_IMAGES = 6

    # MarkItDown is a local, best-effort Route B. It has a narrower input cap than
    # the general upload cap, a bounded output, and never blocks the asyncio loop.
    MARKITDOWN_MAX_INPUT_BYTES = 10 * 1024 * 1024
    MARKITDOWN_MAX_OUTPUT_CHARS = 50_000
    MARKITDOWN_TIMEOUT_SEC = 12.0

    def classify(self, file_name: str, content_type: str | None) -> ResumeFileKind:
        ext = Path(file_name).suffix.lower()
        mime = (content_type or "").lower()
        if ext == ".pdf" or mime.endswith("pdf"):
            return "pdf"
        if ext == ".docx":
            return "docx"
        if ext == ".doc":
            return "doc"
        if ext == ".txt" or mime.startswith("text/plain"):
            return "txt"
        if ext in _IMAGE_EXTENSIONS or mime.startswith("image/"):
            return "image"
        return "unknown"

    def extract(self, *, file_name: str, content_type: str | None, raw_bytes: bytes) -> str:
        kind = self.classify(file_name, content_type)
        if kind == "pdf":
            return self._extract_pdf(raw_bytes)
        if kind == "docx":
            return self._extract_docx(raw_bytes)
        if kind == "doc":
            return ""
        if kind == "image":
            return ""
        if kind == "txt":
            return raw_bytes.decode("utf-8", errors="ignore")[:50_000]
        return raw_bytes.decode("utf-8", errors="ignore")[:50_000]

    def has_scanned_pdf_pages(self, raw_bytes: bytes) -> bool:
        """Detect substantial image-only pages; a small portrait is not OCR evidence.

        A mixed PDF selects vision for the whole document so native-text pages are
        not silently lost. Page-selective OCR/merge is intentionally not guessed here.
        """
        try:
            import fitz

            with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
                for page in doc:
                    text = page.get_text()
                    if sum(c.isalnum() for c in text) >= 40:
                        continue
                    area = page.rect.get_area()
                    image_area = sum(
                        (fitz.Rect(image["bbox"]) & page.rect).get_area()
                        for image in page.get_image_info()
                    )
                    if area and image_area / area >= 0.5:
                        return True
        except Exception:
            # Native text extraction and local Route B remain available.
            logger.warning("PDF page inspection unavailable", exc_info=False)
        return False

    def extract_markdown_route_b(
        self,
        *,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
    ) -> str:
        """Synchronously convert uploaded bytes to Markdown with MarkItDown.

        This function is intentionally local-only: no URL, server-side file path, or
        plugin is supplied. Call :meth:`extract_markdown_route_b_with_timeout` from
        request code so conversion does not block the async event loop.
        """
        kind = self.classify(file_name, content_type)
        if kind not in {"pdf", "docx", "txt"}:
            return ""
        if not raw_bytes or len(raw_bytes) > self.MARKITDOWN_MAX_INPUT_BYTES:
            return ""
        try:
            from markitdown import MarkItDown

            result = MarkItDown(enable_plugins=False).convert_stream(
                io.BytesIO(raw_bytes),
                file_extension=Path(file_name).suffix.lower(),
            )
            markdown = getattr(result, "text_content", "")
            if not isinstance(markdown, str):
                return ""
            return markdown.strip()[: self.MARKITDOWN_MAX_OUTPUT_CHARS]
        except Exception as exc:  # noqa: BLE001 - Route B must degrade safely.
            logger.warning(
                "MarkItDown Route B failed (file=%s kind=%s reason=%s)",
                file_name,
                kind,
                type(exc).__name__,
            )
            return ""

    async def extract_markdown_route_b_with_timeout(
        self,
        *,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
    ) -> str:
        """Run Route B off-loop and fail closed after its bounded request budget."""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self.extract_markdown_route_b,
                    file_name=file_name,
                    content_type=content_type,
                    raw_bytes=raw_bytes,
                ),
                timeout=self.MARKITDOWN_TIMEOUT_SEC,
            )
        except TimeoutError:
            logger.warning(
                "MarkItDown Route B timed out (file=%s timeout_sec=%s)",
                file_name,
                self.MARKITDOWN_TIMEOUT_SEC,
            )
            return ""

    def pdf_page_images(
        self,
        raw_bytes: bytes,
        *,
        max_pages: int | None = None,
        scale: float = 2.0,
        require_all_pages: bool = False,
    ) -> list[tuple[bytes, str]]:
        """Render PDF pages to PNG bytes for vision OCR."""
        limit = max_pages if max_pages is not None else self.PDF_VISION_MAX_PAGES
        try:
            import fitz  # pymupdf
        except ImportError:
            return []

        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception:
            return []

        images: list[tuple[bytes, str]] = []
        try:
            if require_all_pages and len(doc) > limit:
                # Do not label a truncated scan as a completely parsed resume.
                raise ValueError("pdf_vision_page_limit")
            matrix = fitz.Matrix(scale, scale)
            for idx, page in enumerate(doc):
                if idx >= limit:
                    break
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                images.append((pix.tobytes("png"), "image/png"))
        finally:
            doc.close()
        return images

    @classmethod
    def pdf_page_images_from_bytes(
        cls, raw_bytes: bytes, *, max_pages: int | None = None, require_all_pages: bool = False
    ) -> list[tuple[bytes, str]]:
        return cls().pdf_page_images(
            raw_bytes, max_pages=max_pages, require_all_pages=require_all_pages
        )

    def docx_embedded_images(
        self,
        raw_bytes: bytes,
        *,
        max_images: int | None = None,
    ) -> list[tuple[bytes, str]]:
        """Images embedded in Word (word/media/*) for vision OCR of icons/scan snippets."""
        limit = max_images if max_images is not None else self.DOCX_VISION_MAX_IMAGES
        images: list[tuple[bytes, str]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                for name in sorted(zf.namelist()):
                    if not name.startswith("word/media/"):
                        continue
                    suffix = Path(name).suffix.lower()
                    if suffix not in _DOCX_MEDIA_SUFFIXES:
                        continue
                    if suffix in {".emf", ".wmf"}:
                        continue
                    data = zf.read(name)
                    if not data or len(data) > 5_000_000:
                        continue
                    mime = mimetypes.guess_type(name)[0] or "image/png"
                    images.append((data, mime))
                    if len(images) >= limit:
                        break
        except (zipfile.BadZipFile, KeyError):
            return []
        return images

    @staticmethod
    def _extract_pdf(raw_bytes: bytes) -> str:
        try:
            import fitz  # pymupdf
        except ImportError:
            return ""
        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
        except Exception:
            return ""
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
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                xml = zf.read("word/document.xml")
        except (zipfile.BadZipFile, KeyError):
            return ""
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
        if ext in _IMAGE_EXTENSIONS:
            return True
        cleaned = re.sub(r"\s+", "", text)
        if len(cleaned) < 120:
            return True
        return False

    @staticmethod
    def is_pdf(file_name: str, content_type: str | None) -> bool:
        ext = Path(file_name).suffix.lower()
        return ext == ".pdf" or (content_type or "").endswith("pdf")

    @staticmethod
    def is_docx(file_name: str, content_type: str | None) -> bool:
        ext = Path(file_name).suffix.lower()
        mime = (content_type or "").lower()
        return ext == ".docx" or "wordprocessingml" in mime
