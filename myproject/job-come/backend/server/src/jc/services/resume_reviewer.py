"""Pre-export resume draft reviewer (LLM)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jc.config import settings
from jc.llm.router import get_llm_router
from jc.models.enums import ReviewerStatus
from jc.services.role_families import get_playbook

_PROMPT_PATH = Path(__file__).resolve().parents[3].parent / "agent" / "prompts" / "export" / "reviewer.md"


@dataclass(frozen=True, slots=True)
class ReviewerResult:
    status: ReviewerStatus
    notes: str | None
    issues: list[dict[str, Any]]


class ResumeReviewer:
    def __init__(self) -> None:
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def review(
        self,
        *,
        sections: dict[str, Any],
        source_profile: dict[str, Any] | None = None,
        role_family: str | None = None,
    ) -> ReviewerResult:
        if not settings.jc_llm_enabled:
            return ReviewerResult(
                status=ReviewerStatus.FAILED,
                notes="LLM 未启用，导出前自动审稿不可用。请配置 JC_LLM_ENABLED=true。",
                issues=[{"code": "llm_disabled", "message": "Reviewer requires LLM"}],
            )

        if not source_profile:
            return ReviewerResult(status=ReviewerStatus.FAILED, notes="缺少事实档案，无法核验简历。",
                                  issues=[{"code": "missing_source", "message": "Source profile required"}])
        # The playbook decides which *warnings* are legitimate for this audience. Without
        # it the reviewer applies engineering expectations to every role and tells a legal
        # or HR candidate their perfectly good bullet is missing a metric.
        playbook = get_playbook(role_family or sections.get("role_family"))
        # The angles the draft was written from explain why a bullet leads with scale
        # rather than result. Without them the reviewer reports the user's own choice
        # as a `buried_highlight` defect.
        emphases = sections.get("framing_emphases")
        if not isinstance(emphases, list):
            emphases = []
        review_input = json.dumps(
            {
                "sections": sections,
                "source_profile": source_profile,
                "framing_emphases": [str(e) for e in emphases],
                "role_playbook": {
                    "id": playbook.id,
                    "label": playbook.label,
                    "outcome_metrics": list(playbook.outcome_metrics),
                    "object_nouns": list(playbook.object_nouns),
                    "must_haves": list(playbook.must_haves),
                    "quantification_optional": playbook.quantification_optional,
                },
            },
            ensure_ascii=False,
        )
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
        # Only factual/integrity failures block export. Quality warnings are advisory, so a
        # reviewer that reports them cannot lock the user out of their own document. An
        # unrecognised severity is treated as blocking (fail closed).
        if self._has_blocking_issue(issues):
            status = ReviewerStatus.FAILED
        return ReviewerResult(status=status, notes=notes, issues=issues)

    @staticmethod
    def _has_blocking_issue(issues: list[dict[str, Any]]) -> bool:
        for issue in issues:
            severity = str(issue.get("severity") or issue.get("code") or "error").strip().lower()
            if severity != "warning":
                return True
        return False
