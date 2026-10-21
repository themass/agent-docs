"""Bounded resume ingest with evidence-driven strategy selection."""

from __future__ import annotations

import asyncio
import logging
import time
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
from jc.services.ingest_plan import IngestRoute, select_ingest_plan, usable_text
from jc.services.ingest_result import IngestResult
from jc.services.ingest_user_messages import (
    USER_DOC_LEGACY_FORMAT,
    USER_LLM_DISABLED,
    USER_PARSE_INCOMPLETE,
)
from jc.services.profile_ingest_quality import (
    humanize_filename,
    is_low_quality_payload,
)
from jc.services.profile_normalizer import ProfileNormalizer
from jc.services.profile_structurer import ProfileStructurer
from jc.services.profile_vision import ProfileVisionExtractor

logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".txt"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
#: Floor for pasted text. Below this the structurer has nothing to extract and would
#: fill a profile with plausible invention, which is worse than a refusal.
_MIN_TEXT_CHARS = 80
#: Ceiling, so one paste cannot become a model call that times out. Well above a long
#: resume; a user at this length is pasting something other than their career.
_MAX_TEXT_CHARS = 50_000


class IngestValidationError(ValueError):
    pass


class ProfileIngestService:
    def __init__(self) -> None:
        self._extractor = DocumentExtractor()
        self._structurer = ProfileStructurer()
        self._vision = ProfileVisionExtractor()
        self._normalizer = ProfileNormalizer()

    def validate_text(self, text: str) -> None:
        """Gate pasted text before it becomes a source.

        The floor is not a formatting rule — it is the point below which the structurer
        has nothing to work with and would answer by inventing a profile. A user who
        typed one line gets told to write more; they should not get a fabricated
        career back.
        """
        stripped = text.strip()
        if not stripped:
            raise IngestValidationError("内容是空的，请粘贴或输入简历内容。")
        if len(stripped) < _MIN_TEXT_CHARS:
            raise IngestValidationError(
                f"内容太短了（至少 {_MIN_TEXT_CHARS} 字）。"
                "可以粘贴旧简历原文，或写一段你做过什么、带上公司和时间。"
            )
        if len(stripped) > _MAX_TEXT_CHARS:
            raise IngestValidationError(
                f"内容超过 {_MAX_TEXT_CHARS // 10000} 万字，请分几次粘贴或精简后再试。"
            )

    def validate_upload(self, file_name: str, content_type: str | None, size: int) -> None:
        ext = Path(file_name).suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise IngestValidationError(
                f"Unsupported file type '{ext or 'unknown'}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            )
        if size <= 0:
            raise IngestValidationError("Empty file")
        if size > MAX_UPLOAD_BYTES:
            raise IngestValidationError(
                f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
            )

    async def parse(
        self,
        *,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
        on_phase: Callable[[str], Awaitable[None]] | None = None,
    ) -> IngestResult:
        """Template pipeline: extract → select once → execute → validate.

        Only local extraction may fall back to another representation. Model failover
        is exclusively owned by LLMRouter. A gateway outage must never trigger OCR.
        """
        started = time.monotonic()
        run_id = new_id("iprn", length=12)
        stage = "classify"

        async def phase(name: str) -> None:
            nonlocal stage
            stage = name
            logger.info(
                "ingest_pipeline run_id=%s phase=%s elapsed_ms=%d",
                run_id,
                name,
                int((time.monotonic() - started) * 1000),
            )
            if on_phase is not None:
                await on_phase(name)

        try:
            async with asyncio.timeout(settings.jc_ingest_timeout_seconds):
                await phase("classify")
                kind = self._extractor.classify(file_name, content_type)
                await phase("extract_text")
                # PDF/zip/converter work must not block polling or other users.
                text = await asyncio.to_thread(
                    self._extractor.extract,
                    file_name=file_name,
                    content_type=content_type,
                    raw_bytes=raw_bytes,
                )
                if kind == "doc" or not settings.jc_llm_enabled:
                    return IngestResult(
                        payload=self._mock_payload(file_name=file_name, note=text[:500] or None),
                        mode="mock_fallback",
                        warning=USER_DOC_LEGACY_FORMAT if kind == "doc" else USER_LLM_DISABLED,
                    )

                await phase("inspect_document")
                scanned = False
                if kind == "pdf":
                    scanned = await asyncio.to_thread(
                        self._extractor.has_scanned_pdf_pages, raw_bytes
                    )
                extraction_source = "native_text"
                # Fix source extraction BEFORE paying for a model. Never retry the
                # same model pipeline merely because its previous request timed out.
                if kind in {"pdf", "docx"} and not usable_text(text) and not scanned:
                    await phase("extract_markdown")
                    markdown = await self._extractor.extract_markdown_route_b_with_timeout(
                        file_name=file_name, content_type=content_type, raw_bytes=raw_bytes
                    )
                    if usable_text(markdown):
                        text, extraction_source = markdown, "markitdown"
                plan = select_ingest_plan(kind, text, scanned_pages=scanned)
                logger.info(
                    "ingest_pipeline run_id=%s route=%s reason=%s text_chars=%d",
                    run_id,
                    plan.route,
                    plan.reason,
                    len(text),
                )
                if plan.route == IngestRoute.TEXT:
                    if not text.strip():
                        raise IngestValidationError(
                            "没有读到可解析的文字，请上传文字版 PDF、Word 或清晰图片。"
                        )
                    mode = (
                        f"llm_markitdown_{kind}"
                        if extraction_source == "markitdown"
                        else f"llm_text_{'plain' if kind == 'txt' else kind}"
                    )
                    await phase(mode)
                    payload = await self._structurer.structure(text=text, source_file=file_name)
                elif plan.route == IngestRoute.PDF_VISION:
                    await phase("llm_vision_pdf")
                    payload = await self._vision.extract_pdf(
                        file_name=file_name, raw_bytes=raw_bytes
                    )
                    mode = extraction_source = "vision_pdf"
                elif plan.route == IngestRoute.IMAGE_VISION:
                    await phase("llm_vision_image")
                    payload = await self._vision.extract(
                        file_name=file_name, raw_bytes=raw_bytes, content_type=content_type
                    )
                    mode = extraction_source = "vision_image"
                else:
                    embedded = await asyncio.to_thread(
                        self._extractor.docx_embedded_images, raw_bytes
                    )
                    if not embedded:
                        raise IngestValidationError(
                            "未读到文字或可识别图片，请转换为文字版 PDF 后重试。"
                        )
                    await phase("llm_vision_docx")
                    payload = await self._vision.extract_embedded_images(
                        file_name=file_name, images=embedded, context="Scanned Word document"
                    )
                    mode = extraction_source = "vision_docx_media"
                await phase("pick_best")  # Retain persisted phase vocabulary for older clients.
                payload = self._normalizer.normalize(payload)
                warning = (
                    USER_PARSE_INCOMPLETE
                    if is_low_quality_payload(payload, file_name=file_name)
                    else None
                )
                logger.info(
                    "ingest_pipeline run_id=%s completed route=%s elapsed_ms=%d",
                    run_id,
                    plan.route,
                    int((time.monotonic() - started) * 1000),
                )
                return IngestResult(
                    payload=payload, mode=mode, warning=warning, extraction_source=extraction_source
                )
        except TimeoutError as exc:
            logger.warning(
                "ingest_pipeline run_id=%s timeout phase=%s budget=%s elapsed_ms=%d",
                run_id,
                stage,
                settings.jc_ingest_timeout_seconds,
                int((time.monotonic() - started) * 1000),
            )
            raise IngestValidationError(
                "解析等待超时，未生成档案。原文件已保留，可以重试解析。"
            ) from exc
        except IngestValidationError:
            raise
        except Exception as exc:
            logger.warning(
                "ingest_pipeline run_id=%s failed phase=%s error_type=%s elapsed_ms=%d",
                run_id,
                stage,
                type(exc).__name__,
                int((time.monotonic() - started) * 1000),
            )
            if str(exc) == "llm_timeout":
                message = (
                    "已读取简历文字，但模型服务响应超时，未生成档案。"
                    "原文件已保留，无需修改文件格式；请稍后重试。"
                )
            elif str(exc) == "llm_call_failed":
                message = (
                    "已读取简历文字，但模型服务暂时不可用，未生成档案。"
                    "原文件已保留，无需修改文件格式；请稍后重试。"
                )
            elif str(exc) in {
                "invalid_json_response", "empty_model_response", "invalid_profile_schema",
                "invalid_profile_response", "empty_profile_response",
            }:
                message = "已读取简历文字，但模型未返回有效档案。原文件已保留，本次未保存解析结果。"
            elif str(exc) == "pdf_vision_page_limit":
                message = (
                    "扫描或混合 PDF 页数超过识别上限，请拆分文件或上传文字版 Word/PDF；"
                    "本次未生成档案。"
                )
            else:
                message = (
                    "本次简历解析未完成，原文件已保留。请稍后重试或上传文字版文件；"
                    "不会将失败结果当作已完成档案。"
                )
            raise IngestValidationError(message) from exc

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
