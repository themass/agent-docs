"""LLM: resume text → ProfilePayload."""

from __future__ import annotations

from typing import Any

from jc.config import settings
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.paths import prompt_file
from jc.schemas.profile_payload import ProfilePayload
from jc.services.profile_ingest_contract import (
    ProfileStructureError,
    parse_profile_json as parse_profile_json,
    validate_profile_content,
)

_PROMPT_PATH = prompt_file("ingest", "profile_structurer.md")


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
            return validate_profile_content(
                router.content_from_response(response), source_file=source_file
            )

        try:
            profile = await router.acompletion(
                "ingest_fast",
                log_context=llm_context("profile_structurer"),
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Source file: {source_file}\n\nResume text:\n{text}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout_seconds=settings.jc_ingest_attempt_timeout_seconds,
                buffered_stream=True,
                stream_attempt_timeout_seconds=settings.jc_ingest_stream_attempt_seconds,
                response_validator=validate_response,
            )
        except ProfileStructureError:
            # Raised by validate_response (bad JSON/schema) and re-raised as-is by
            # litellm once every endpoint in the fallback chain has rejected the
            # same malformed answer. The reason code set above is still accurate.
            raise
        except Exception as exc:  # noqa: BLE001
            # Every endpoint in the fallback chain failed for a reason other than
            # the validator rejecting their answer - connection/timeout/auth, not
            # a schema problem. Keep that distinction: collapsing it into
            # "invalid_profile_schema" hides real gateway outages behind a label
            # that reads like a model-quality issue and sends whoever is
            # debugging looking at the prompt instead of the network.
            from jc.llm.call_log import error_code_for

            code = "llm_timeout" if error_code_for(exc) == "timeout" else "llm_call_failed"
            raise ProfileStructureError(code) from exc
        if not isinstance(profile, ProfilePayload):  # Defensive guard for custom routers/tests.
            raise ProfileStructureError("invalid_profile_response")
        return profile
