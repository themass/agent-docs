"""Extract structured profile from resume images via vision LLM."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from jc.config import settings
from jc.llm.router import get_llm_router
from jc.schemas.profile_payload import ProfilePayload

_PROMPT_PATH = Path(__file__).resolve().parents[3].parent / "agent" / "prompts" / "ingest" / "profile_vision.md"


class ProfileVisionExtractor:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def extract(self, *, file_name: str, raw_bytes: bytes, content_type: str | None) -> ProfilePayload:
        if not settings.jc_llm_enabled:
            raise RuntimeError("LLM disabled")

        mime = content_type or mimetypes.guess_type(file_name)[0] or "image/png"
        return await self._vision_json(
            file_name=file_name,
            intro=f"Source file: {file_name}\nExtract resume fields as JSON.",
            images=[(raw_bytes, mime)],
        )

    async def extract_pdf(self, *, file_name: str, raw_bytes: bytes) -> ProfilePayload:
        """OCR structured profile from PDF pages (vision model)."""
        if not settings.jc_llm_enabled:
            raise RuntimeError("LLM disabled")

        from jc.services.document_extractor import DocumentExtractor

        pages = DocumentExtractor.pdf_page_images_from_bytes(raw_bytes)
        if not pages:
            raise ValueError("Could not render PDF pages for vision OCR")

        return await self._vision_json(
            file_name=file_name,
            intro=(
                f"Source file: {file_name}\n"
                f"Pages: {len(pages)}\n"
                "Extract full resume fields as JSON. Merge content across all pages."
            ),
            images=pages,
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
            images=images,
            page_labels=True,
        )

    async def _vision_json(
        self,
        *,
        file_name: str,
        intro: str,
        images: list[tuple[bytes, str]],
        page_labels: bool = False,
    ) -> ProfilePayload:
        content: list[dict[str, object]] = [{"type": "text", "text": intro}]
        for idx, (raw, mime) in enumerate(images, start=1):
            if page_labels:
                content.append({"type": "text", "text": f"--- Part {idx} ---"})
            b64 = base64.standard_b64encode(raw).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )

        router = get_llm_router()
        response = await router.acompletion(
            "vision",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        data = json.loads(router.content_from_response(response))
        profile = ProfilePayload.model_validate(data)
        profile.meta.source_file = file_name
        return profile
