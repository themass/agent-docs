"""LLM: resume text → ProfilePayload."""

from __future__ import annotations

import json
from pathlib import Path

from jobcome.config import settings
from jobcome.llm.router import get_llm_router
from jobcome.schemas.profile_payload import ProfilePayload

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "ingest" / "profile_structurer.md"


class ProfileStructurer:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def structure(self, *, text: str, source_file: str) -> ProfilePayload:
        if not settings.job_come_llm_enabled:
            raise RuntimeError("LLM disabled")
        if not text.strip():
            raise ValueError("No extractable text")

        router = get_llm_router()
        response = await router.acompletion(
            "ingest_fast",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": f"Source file: {source_file}\n\nResume text:\n{text[:30_000]}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = router.content_from_response(response)
        data = json.loads(content)
        profile = ProfilePayload.model_validate(data)
        profile.meta.source_file = source_file
        return profile
