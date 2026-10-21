"""Extract structured profile from resume images via vision LLM."""

from __future__ import annotations

import asyncio
from typing import Any

from jc.config import settings
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.llm.vision import ImageRef, build_vision_content
from jc.paths import prompt_file
from jc.schemas.profile_payload import ProfilePayload
from jc.services.profile_ingest_contract import validate_profile_content

_PROMPT_PATH = prompt_file("ingest", "profile_vision.md")


class ProfileVisionExtractor:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def extract(
        self, *, file_name: str, raw_bytes: bytes, content_type: str | None
    ) -> ProfilePayload:
        if not settings.jc_llm_enabled:
            raise RuntimeError("LLM disabled")

        return await self._vision_json(
            file_name=file_name,
            intro=f"Source file: {file_name}\nExtract resume fields as JSON.",
            images=[ImageRef.from_bytes(raw_bytes, mime=content_type, file_name=file_name)],
        )

    async def extract_pdf(self, *, file_name: str, raw_bytes: bytes) -> ProfilePayload:
        """OCR structured profile from PDF pages (vision model)."""
        if not settings.jc_llm_enabled:
            raise RuntimeError("LLM disabled")

        from jc.services.document_extractor import DocumentExtractor

        pages = await asyncio.to_thread(
            DocumentExtractor.pdf_page_images_from_bytes, raw_bytes, require_all_pages=True
        )
        if not pages:
            raise ValueError("Could not render PDF pages for vision OCR")

        return await self._vision_json(
            file_name=file_name,
            intro=(
                f"Source file: {file_name}\n"
                f"Pages: {len(pages)}\n"
                "Extract full resume fields as JSON. Merge content across all pages."
            ),
            images=[ImageRef.from_bytes(raw, mime=mime) for raw, mime in pages],
            page_labels=True,
        )

    async def extract_embedded_images(
        self,
        *,
        file_name: str,
        images: list[tuple[bytes, str]],
        context: str,
    ) -> ProfilePayload:
        if not settings.jc_llm_enabled:
            raise RuntimeError("LLM disabled")
        if not images:
            raise ValueError("No embedded images to parse")
        return await self._vision_json(
            file_name=file_name,
            intro=(
                f"Source file: {file_name}\n"
                f"Context: {context}\n"
                f"Embedded images: {len(images)}\n"
                "Extract resume fields as JSON. Merge with any visible text in the images."
            ),
            images=[ImageRef.from_bytes(raw, mime=mime) for raw, mime in images],
            page_labels=True,
        )

    async def _vision_json(
        self,
        *,
        file_name: str,
        intro: str,
        images: list[ImageRef],
        page_labels: bool = False,
    ) -> ProfilePayload:
        content = build_vision_content(intro=intro, images=images, part_labels=page_labels)
        router = get_llm_router()

        def validate(response: Any) -> ProfilePayload:
            return validate_profile_content(
                router.content_from_response(response), source_file=file_name
            )

        # OCR of a scanned resume is the single most failure-prone call in the
        # product, so an unreadable answer has to be able to try another model
        # rather than ending the upload.
        return await router.acompletion(
            "vision",
            log_context=llm_context("profile_vision"),
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            timeout_seconds=settings.jc_ingest_attempt_timeout_seconds,
            response_validator=validate,
        )
