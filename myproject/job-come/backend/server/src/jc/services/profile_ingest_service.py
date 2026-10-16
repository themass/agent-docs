"""Resume ingest — multi-route parse: text layer + vision for PDF/Word/images."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from agentkit.common.ids import new_id

from jc.config import settings
from jc.models.enums import ConfidenceLevel
from jc.schemas.profile_payload import (
    ProfileContact,
    ProfileEducation,
    ProfileExperience,
    ProfileMeta,
    ProfilePayload,
)
from jc.services.document_extractor import DocumentExtractor
from jc.services.ingest_result import IngestResult
from jc.services.ingest_user_messages import (
    USER_DOC_LEGACY_FORMAT,
    USER_LLM_DISABLED,
    USER_LLM_PARSE_UNAVAILABLE,
    USER_PARSE_INCOMPLETE,
)
from jc.services.profile_ingest_quality import (
    humanize_filename,
    is_low_quality_payload,
    payload_quality_score,
)
from jc.services.profile_normalizer import ProfileNormalizer
from jc.services.profile_structurer import ProfileStructurer
from jc.services.profile_vision import ProfileVisionExtractor

logger = logging.getLogger(__name__)

_DOCX_SKIP_VISION_MIN_SCORE = 35
_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".txt"}
_MAX_BYTES = 15 * 1024 * 1024


class IngestValidationError(ValueError):
    pass


class ProfileIngestService:
    def __init__(self) -> None:
        self._extractor = DocumentExtractor()
        self._structurer = ProfileStructurer()
        self._vision = ProfileVisionExtractor()
        self._normalizer = ProfileNormalizer()

    def validate_upload(self, file_name: str, content_type: str | None, size: int) -> None:
        ext = Path(file_name).suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise IngestValidationError(
                f"Unsupported file type '{ext or 'unknown'}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            )
        if size <= 0:
            raise IngestValidationError("Empty file")
        if size > _MAX_BYTES:
            raise IngestValidationError(f"File too large (max {_MAX_BYTES // (1024 * 1024)} MB)")

    async def parse(
        self,
        *,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
        on_phase: Callable[[str], Awaitable[None]] | None = None,
    ) -> IngestResult:
        async def phase(name: str) -> None:
            if on_phase is not None:
                await on_phase(name)

        await phase("classify")
        kind = self._extractor.classify(file_name, content_type)
        await phase("extract_text")
        text = self._extractor.extract(
            file_name=file_name,
            content_type=content_type,
            raw_bytes=raw_bytes,
        )
        if kind == "doc":
            logger.info("Legacy .doc upload rejected for parse: %s", file_name)
            return IngestResult(
                payload=self._mock_payload(file_name=file_name, note=text[:500] if text else None),
                mode="mock_fallback",
                warning=USER_DOC_LEGACY_FORMAT,
            )

        if not settings.jc_llm_enabled:
            logger.info("Profile ingest placeholder: LLM disabled (file=%s)", file_name)
            return IngestResult(
                payload=self._mock_payload(file_name=file_name, note=text[:500] if text else None),
                mode="mock_fallback",
                warning=USER_LLM_DISABLED,
            )

        failures: list[str] = []
        candidates: list[tuple[str, str, ProfilePayload]] = []

        async def _try_text(
            mode: str,
            source_text: str = text,
            *,
            extraction_source: str = "native_text",
        ) -> None:
            if not source_text.strip():
                return
            await phase(mode)
            try:
                payload = self._normalizer.normalize(
                    await self._structurer.structure(text=source_text, source_file=file_name)
                )
                candidates.append((mode, extraction_source, payload))
            except Exception as exc:  # noqa: BLE001
                # Do not log source_text: a resume contains personal data.
                logger.warning(
                    "Profile structuring failed (file=%s mode=%s reason=%s)",
                    file_name,
                    mode,
                    exc,
                )
                failures.append(f"{mode}: {exc}")

        async def _try_markdown_route_b(mode: str) -> None:
            markdown = await self._extractor.extract_markdown_route_b_with_timeout(
                file_name=file_name,
                content_type=content_type,
                raw_bytes=raw_bytes,
            )
            if not markdown:
                return
            await _try_text(mode, markdown, extraction_source="markitdown")

        async def _try_vision_pdf() -> None:
            if kind != "pdf":
                return
            await phase("llm_vision_pdf")
            try:
                payload = self._normalizer.normalize(
                    await self._vision.extract_pdf(file_name=file_name, raw_bytes=raw_bytes)
                )
                candidates.append(("vision_pdf", "vision_pdf", payload))
            except Exception as exc:  # noqa: BLE001
                logger.exception("PDF vision extract failed for %s: %s", file_name, exc)
                failures.append(f"vision_pdf: {exc}")

        async def _try_vision_docx_media() -> None:
            if kind != "docx":
                return
            embedded = self._extractor.docx_embedded_images(raw_bytes)
            if not embedded:
                return
            await phase("llm_vision_docx")
            try:
                payload = self._normalizer.normalize(
                    await self._vision.extract_embedded_images(
                        file_name=file_name,
                        images=embedded,
                        context=(
                            "Word document with embedded pictures (may include scanned sections)."
                        ),
                    )
                )
                candidates.append(("vision_docx_media", "vision_docx_media", payload))
            except Exception as exc:  # noqa: BLE001
                logger.exception("DOCX vision extract failed for %s: %s", file_name, exc)
                failures.append(f"vision_docx_media: {exc}")

        async def _try_vision_image() -> None:
            if kind != "image":
                return
            await phase("llm_vision_image")
            try:
                payload = self._normalizer.normalize(
                    await self._vision.extract(
                        file_name=file_name,
                        raw_bytes=raw_bytes,
                        content_type=content_type,
                    )
                )
                candidates.append(("vision_image", "vision_image", payload))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Vision extract failed for %s: %s", file_name, exc)
                failures.append(f"vision_image: {exc}")

        # Multi-route matrix (see docs/architecture/TECH-LLM.md §2)
        if kind == "image":
            await _try_vision_image()
        elif kind == "pdf":
            # Keep Route B tied to the text path. A successful vision result must not
            # hide a failed/low-quality text extraction, and Route B remains bounded.
            await _try_text("llm_text_pdf")
            text_score = max(
                (
                    payload_quality_score(payload, file_name=file_name)
                    for mode, _source, payload in candidates
                    if mode == "llm_text_pdf"
                ),
                default=0,
            )
            if text_score < _DOCX_SKIP_VISION_MIN_SCORE:
                await _try_markdown_route_b("llm_markitdown_pdf")
            await _try_vision_pdf()
        elif kind == "docx":
            await _try_text("llm_text_docx")
            text_score = max(
                (payload_quality_score(p, file_name=file_name) for _, _, p in candidates),
                default=0,
            )
            if text_score < _DOCX_SKIP_VISION_MIN_SCORE:
                await _try_markdown_route_b("llm_markitdown_docx")
            text_score = max(
                (payload_quality_score(p, file_name=file_name) for _, _, p in candidates),
                default=0,
            )
            if text_score < _DOCX_SKIP_VISION_MIN_SCORE:
                await _try_vision_docx_media()
            else:
                logger.info(
                    "DOCX text route sufficient (score=%s), skipping embedded-image vision: %s",
                    text_score,
                    file_name,
                )
        elif kind == "txt":
            await _try_text("llm_text_plain")
        else:
            if text.strip():
                await _try_text("llm_text")

        await phase("pick_best")
        if candidates:
            best_mode, extraction_source, best_payload = max(
                candidates,
                key=lambda item: payload_quality_score(item[2], file_name=file_name),
            )
            warning = None
            if is_low_quality_payload(best_payload, file_name=file_name):
                warning = USER_PARSE_INCOMPLETE
            if failures:
                logger.warning(
                    "Profile ingest partial success for %s (mode=%s); other routes: %s",
                    file_name,
                    best_mode,
                    "; ".join(failures),
                )
            return IngestResult(
                payload=best_payload,
                mode=best_mode,
                warning=warning,
                extraction_source=extraction_source,
            )

        detail = "; ".join(failures) if failures else f"no_route_matched kind={kind}"
        logger.error("Profile ingest exhausted all routes for %s: %s", file_name, detail)
        return IngestResult(
            payload=self._mock_payload(file_name=file_name, note=text[:500] if text else None),
            mode="mock_fallback",
            warning=USER_LLM_PARSE_UNAVAILABLE,
        )

    def _mock_payload(self, *, file_name: str, note: str | None) -> ProfilePayload:
        display_name = humanize_filename(Path(file_name).stem) or "待确认姓名"
        now = datetime.now(UTC)
        summary = f"（解析草稿）请核对从「{file_name}」提取的内容。"
        if note:
            summary += f"\n\n提取片段：{note[:400]}"
        return ProfilePayload(
            contact=ProfileContact(
                name=display_name,
                email=None,
                phone=None,
                location=None,
                links=[],
            ),
            summary=summary,
            experiences=[
                ProfileExperience(
                    id=new_id("exp", length=12),
                    company="待确认公司",
                    title="待确认职位",
                    start_date="2020-01",
                    end_date=None,
                    location=None,
                    highlights=["请补充或修改本段经历要点"],
                    skills=[],
                    confidence=ConfidenceLevel.NEEDS_REVIEW,
                )
            ],
            education=[
                ProfileEducation(
                    id=new_id("edu", length=12),
                    school="待确认学校",
                    degree=None,
                    major=None,
                    start_date=None,
                    end_date=None,
                    confidence=ConfidenceLevel.NEEDS_REVIEW,
                )
            ],
            meta=ProfileMeta(source_file=file_name, created_at=now, confirmed_at=None),
        )
