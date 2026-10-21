"""Parse job descriptions via LLM."""

from __future__ import annotations

import json
from typing import Any

from jc.config import settings
from jc.domain.jd_integrity import inspect_jd_text
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.paths import prompt_file
from jc.schemas.job import JDParseResult

_PROMPT_PATH = prompt_file("ingest", "jd_parser.md")


class JdParserService:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def parse(self, *, raw_text: str) -> JDParseResult:
        integrity = inspect_jd_text(raw_text)
        if not settings.jc_llm_enabled:
            return self._heuristic_parse(raw_text).model_copy(update={"integrity": integrity})

        router = get_llm_router()

        def validate(response: Any) -> JDParseResult:
            data = json.loads(router.content_from_response(response))
            return JDParseResult.model_validate(data).model_copy(update={"integrity": integrity})

        # Validating through the router rather than after it: a model that
        # answers 200 with unparseable JSON then fails over to the next
        # endpoint, instead of surfacing as a 500 on a parse the user cannot fix.
        return await router.acompletion(
            "ingest_fast",
            log_context=llm_context("jd_parser"),
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "untrusted_content": True,
                            "integrity": integrity,
                            "jd_text": raw_text[:40_000],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            response_validator=validate,
        )

    @staticmethod
    def _heuristic_parse(raw_text: str) -> JDParseResult:
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        title = lines[0][:120] if lines else "待确认职位"
        company = lines[1][:120] if len(lines) > 1 else None
        return JDParseResult(
            company=company,
            role_title=title,
            keywords=[],
        )
