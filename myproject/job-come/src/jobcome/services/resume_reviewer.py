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

    async def review(self, *, sections: dict[str, Any], source_profile: dict[str, Any] | None = None) -> ReviewerResult:
        if not settings.job_come_llm_enabled:
            return ReviewerResult(
                status=ReviewerStatus.FAILED,
                notes="LLM 未启用，导出前自动审稿不可用。请配置 JOB_COME_LLM_ENABLED=true。",
                issues=[{"code": "llm_disabled", "message": "Reviewer requires LLM"}],
            )

        if not source_profile:
            return ReviewerResult(status=ReviewerStatus.FAILED, notes="缺少事实档案，无法核验简历。",
                                  issues=[{"code": "missing_source", "message": "Source profile required"}])
        review_input = json.dumps({"sections": sections, "source_profile": source_profile}, ensure_ascii=False)
        if len(review_input) > 100_000:
            return ReviewerResult(status=ReviewerStatus.FAILED, notes="内容超过审稿上限，请精简后重试。",
                                  issues=[{"code": "input_too_large", "message": "Review input too large"}])

        router = get_llm_router()
        response = await router.acompletion(
            "flash",
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": review_input,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        try:
            data = json.loads(router.content_from_response(response))
        except (ValueError, TypeError):
            return ReviewerResult(status=ReviewerStatus.FAILED, notes="审稿返回格式错误，请重试。",
                                  issues=[{"code": "invalid_json", "message": "Invalid review JSON"}])
        if not isinstance(data, dict) or data.get("status") not in {"passed", "failed"} or not isinstance(data.get("issues"), list):
            return ReviewerResult(status=ReviewerStatus.FAILED, notes="审稿返回格式不完整，请重试。", issues=[{"code": "invalid_review", "message": "Invalid review contract"}])
        if not all(isinstance(issue, dict) for issue in data["issues"]):
            return ReviewerResult(status=ReviewerStatus.FAILED, notes="审稿问题格式不完整，请重试。", issues=[{"code": "invalid_issues", "message": "Invalid issues"}])
        status_raw = data["status"]
        status = ReviewerStatus.PASSED if status_raw == "passed" else ReviewerStatus.FAILED
        issues = list(data.get("issues") or [])
        summary = data.get("summary")
        notes = summary if isinstance(summary, str) else None
        if issues and status == ReviewerStatus.PASSED:
            status = ReviewerStatus.FAILED
        return ReviewerResult(status=status, notes=notes, issues=issues)
