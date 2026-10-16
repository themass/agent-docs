"""LLM: resume text → ProfilePayload."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from jc.config import settings
from jc.llm.router import get_llm_router
from jc.schemas.profile_payload import ProfilePayload

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3].parent
    / "agent"
    / "prompts"
    / "ingest"
    / "profile_structurer.md"
)
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.IGNORECASE | re.DOTALL)


class ProfileStructureError(RuntimeError):
    """A safe, actionable reason why a model response cannot form a profile."""


def parse_profile_json(content: str) -> dict[str, Any]:
    """Parse one JSON object, tolerating a model's accidental Markdown fence.

    Do not include response content in error messages: resumes can contain personal data and
    errors are persisted in ingest logs.
    """
    text = content.strip()
    if not text:
        raise ProfileStructureError("empty_model_response")

    fenced = _CODE_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    if not text:
        raise ProfileStructureError("empty_model_response")

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileStructureError("invalid_json_response") from exc
    if not isinstance(value, dict):
        raise ProfileStructureError("invalid_json_object")
    return value


class ProfileStructurer:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def structure(self, *, text: str, source_file: str) -> ProfilePayload:
        if not settings.jc_llm_enabled:
            raise RuntimeError("LLM disabled")
        if not text.strip():
            raise ValueError("No extractable text")

        router = get_llm_router()

        def validate_response(response: Any) -> ProfilePayload:
            data = parse_profile_json(router.content_from_response(response))
            try:
                profile = ProfilePayload.model_validate(data)
            except ValidationError as exc:
                raise ProfileStructureError("invalid_profile_schema") from exc
            profile.meta.source_file = source_file
            return profile

        profile = await router.acompletion(
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
            response_validator=validate_response,
        )
        if not isinstance(profile, ProfilePayload):  # Defensive guard for custom routers/tests.
            raise ProfileStructureError("invalid_profile_response")
        return profile
