"""Pre-export resume draft reviewer (LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jobcome.config import settings
from jobcome.llm.router import get_llm_router
from jobcome.models.enums import ReviewerStatus

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "export" / "reviewer.md"


@dataclass(frozen=True, slots=True)
class ReviewerResult:
    status: ReviewerStatus
    notes: str | None
    issues: list[dict[str, Any]]


class ResumeReviewer:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def review(self, *, sections: dict[str, Any]) -> ReviewerResult:
        if not settings.job_come_llm_enabled:
            return ReviewerResult(
                status=ReviewerStatus.FAILED,
                notes="LLM 未启用，导出前自动审稿不可用。请配置 JOB_COME_LLM_ENABLED=true。",
                issues=[{"code": "llm_disabled", "message": "Reviewer requires LLM"}],
            )

        router = get_llm_router()
        response = await router.acompletion(
            "flash",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": json.dumps({"sections": sections}, ensure_ascii=False)[:40_000],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(router.content_from_response(response))
        status_raw = data.get("status", "passed")
        status = ReviewerStatus.PASSED if status_raw == "passed" else ReviewerStatus.FAILED
        issues = list(data.get("issues") or [])
        summary = data.get("summary")
        notes = summary if isinstance(summary, str) else None
        if issues and status == ReviewerStatus.PASSED:
            status = ReviewerStatus.FAILED
        return ReviewerResult(status=status, notes=notes, issues=issues)
