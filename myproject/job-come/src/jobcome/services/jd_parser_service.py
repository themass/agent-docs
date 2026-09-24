"""Parse job descriptions via LLM."""

from __future__ import annotations

import json
from pathlib import Path

from jobcome.config import settings
from jobcome.llm.router import get_llm_router
from jobcome.schemas.job import JDParseResult

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "ingest" / "jd_parser.md"


class JdParserService:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def parse(self, *, raw_text: str) -> JDParseResult:
        if not settings.job_come_llm_enabled:
            return self._heuristic_parse(raw_text)

        router = get_llm_router()
        response = await router.acompletion(
            "ingest_fast",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": raw_text[:40_000]},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        data = json.loads(router.content_from_response(response))
        return JDParseResult.model_validate(data)

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
