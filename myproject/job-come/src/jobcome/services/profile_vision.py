"""Extract structured profile from resume images via vision LLM."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from jobcome.config import settings
from jobcome.llm.router import get_llm_router
from jobcome.schemas.profile_payload import ProfilePayload

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "ingest" / "profile_vision.md"


class ProfileVisionExtractor:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def extract(self, *, file_name: str, raw_bytes: bytes, content_type: str | None) -> ProfilePayload:
        if not settings.job_come_llm_enabled:
            raise RuntimeError("LLM disabled")

        mime = content_type or mimetypes.guess_type(file_name)[0] or "image/png"
        b64 = base64.standard_b64encode(raw_bytes).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"

        router = get_llm_router()
        response = await router.acompletion(
            "vision",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Source file: {file_name}\nExtract resume fields as JSON."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = router.content_from_response(response)
        data = json.loads(content)
        profile = ProfilePayload.model_validate(data)
        profile.meta.source_file = file_name
        return profile

    async def extract_pdf(self, *, file_name: str, raw_bytes: bytes) -> ProfilePayload:
        """OCR structured profile from PDF pages (vision model)."""
        if not settings.job_come_llm_enabled:
            raise RuntimeError("LLM disabled")

        from jobcome.services.document_extractor import DocumentExtractor

        pages = DocumentExtractor.pdf_page_images(raw_bytes, max_pages=3)
        if not pages:
            raise ValueError("Could not render PDF pages for vision OCR")

        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    f"Source file: {file_name}\n"
                    f"Pages: {len(pages)}\n"
                    "Extract full resume fields as JSON. Merge content across all pages."
                ),
            }
        ]
        import base64

        for idx, (png_bytes, mime) in enumerate(pages, start=1):
            b64 = base64.standard_b64encode(png_bytes).decode("ascii")
            content.append(
                {
                    "type": "text",
                    "text": f"--- Page {idx} ---",
                }
            )
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
