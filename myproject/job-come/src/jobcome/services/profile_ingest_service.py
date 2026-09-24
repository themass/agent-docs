"""Resume ingest — extract text, structure via LLM, vision fallback for PDF/images."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from agentkit.common.ids import new_id

from jobcome.config import settings
from jobcome.models.enums import ConfidenceLevel
from jobcome.schemas.profile_payload import (
    ProfileContact,
    ProfileEducation,
    ProfileExperience,
    ProfileMeta,
    ProfilePayload,
)
from jobcome.services.document_extractor import DocumentExtractor
from jobcome.services.ingest_result import IngestResult
from jobcome.services.profile_ingest_quality import (
    humanize_filename,
    is_low_quality_payload,
    payload_quality_score,
)
from jobcome.services.profile_normalizer import ProfileNormalizer
from jobcome.services.profile_structurer import ProfileStructurer
from jobcome.services.profile_vision import ProfileVisionExtractor

logger = logging.getLogger(__name__)

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
    ) -> IngestResult:
        text = self._extractor.extract(
            file_name=file_name,
            content_type=content_type,
            raw_bytes=raw_bytes,
        )
        scanned = self._extractor.is_probably_scanned(text, file_name=file_name)
        is_pdf = self._extractor.is_pdf(file_name, content_type)

        if not settings.job_come_llm_enabled:
            return IngestResult(
                payload=self._mock_payload(file_name=file_name, note=text[:500] if text else None),
                mode="mock_fallback",
                warning=(
                    "未启用 LLM（JOB_COME_LLM_ENABLED=false）。当前为占位解析，"
                    "请在 .env 设置 JOB_COME_LLM_ENABLED=true 并配置 YUAI_API_KEY 后重新上传。"
                ),
            )

        errors: list[str] = []
        candidates: list[tuple[str, ProfilePayload, str | None]] = []

        async def _try_text(mode: str) -> None:
            if not text.strip():
                return
            try:
                payload = self._normalizer.normalize(
                    await self._structurer.structure(text=text, source_file=file_name)
                )
                candidates.append((mode, payload, None))
            except Exception as exc:  # noqa: BLE001
                logger.warning("ProfileStructurer failed for %s: %s", file_name, exc)
                errors.append(f"文本结构化失败: {exc}")

        async def _try_vision_pdf() -> None:
            if not is_pdf:
                return
            try:
                payload = self._normalizer.normalize(
                    await self._vision.extract_pdf(file_name=file_name, raw_bytes=raw_bytes)
                )
                candidates.append(("vision_pdf", payload, None))
            except Exception as exc:  # noqa: BLE001
                logger.warning("PDF vision extract failed for %s: %s", file_name, exc)
                errors.append(f"PDF 视觉解析失败: {exc}")

        async def _try_vision_image() -> None:
            ext = Path(file_name).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
                return
            try:
                payload = self._normalizer.normalize(
                    await self._vision.extract(
                        file_name=file_name,
                        raw_bytes=raw_bytes,
                        content_type=content_type,
                    )
                )
                candidates.append(("vision_image", payload, None))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vision extract failed for %s: %s", file_name, exc)
                errors.append(f"图片视觉解析失败: {exc}")

        # PDF: vision OCR first (styled resumes), then text layer
        if is_pdf:
            await _try_vision_pdf()
            if not scanned:
                await _try_text("llm_text")
        else:
            if not scanned:
                await _try_text("llm_text")
            await _try_vision_image()

        if scanned and not is_pdf:
            await _try_vision_image()
            await _try_text("llm_text_low_quality")

        if candidates:
            best_mode, best_payload, _ = max(
                candidates,
                key=lambda item: payload_quality_score(item[1], file_name=file_name),
            )
            warning = errors[0] if errors and is_low_quality_payload(best_payload, file_name=file_name) else None
            if is_low_quality_payload(best_payload, file_name=file_name):
                warning = warning or "解析结果不完整，请核对或让 Agent 补全经历。"
            return IngestResult(payload=best_payload, mode=best_mode, warning=warning)

        detail = "；".join(errors) if errors else "无法从文件中提取有效文本"
        return IngestResult(
            payload=self._mock_payload(file_name=file_name, note=text[:500] if text else None),
            mode="mock_fallback",
            warning=(
                f"LLM 解析全部失败，已回退占位数据。请检查 YUAI_API_KEY / 模型路由。详情：{detail}"
            ),
        )

    def _mock_payload(self, *, file_name: str, note: str | None) -> ProfilePayload:
        display_name = humanize_filename(Path(file_name).stem) or "待确认姓名"
        now = datetime.now(UTC)
        summary = f"（解析草稿）请核对从「{file_name}」提取的内容。"
        if note:
            summary += f"\n\n提取片段：{note[:400]}"
        return ProfilePayload(
            contact=ProfileContact(name=display_name, email=None, phone=None, location=None, links=[]),
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
