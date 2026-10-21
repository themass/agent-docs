"""Pre-export resume draft reviewer (LLM)."""

from __future__ import annotations

import asyncio
import json
import copy
import logging
import time
from dataclasses import dataclass
from typing import Any

from jc.config import settings
from jc.domain.role_families import RolePlaybook, get_playbook
from jc.llm.call_context import llm_context
from jc.llm.router import get_llm_router
from jc.models.enums import ReviewerStatus
from jc.skills.composer import compose_writing_prompt

#: The reviewer reads its own skill package, and it loads the same `method` and
#: `structure` layers the writer was given — expressed from the judging side. The
#: two must come from one place: a reviewer applying a different bar than the writer
#: was told to meet reports the system's own choices back to the user as defects.
_SKILL_ID = "resume-reviewer"
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReviewerResult:
    status: ReviewerStatus
    notes: str | None
    issues: list[dict[str, Any]]
    # Did the reviewer actually reach a verdict about this draft?
    #
    # This is not the same question as `status`. "The reviewer read the draft and found
    # an unsupported number" and "the gateway was down" both used to arrive here as
    # FAILED, and the download was locked either way -- so an outage looked to the user
    # exactly like being accused of making things up, with no way out of either.
    #
    # `available=False` means we have no opinion about the draft. Nothing downstream may
    # treat it as a finding, and it must never be the reason a download is withheld:
    # the user cannot fix our gateway.
    available: bool = True


class ResumeReviewer:
    @staticmethod
    def _compose_system_prompt(playbook: RolePlaybook) -> str:
        """Reviewer prompt for this family.

        Composed per review rather than once per process: which warnings are
        legitimate is a per-family decision, and that is exactly what a single
        cached prompt could not express.
        """
        return compose_writing_prompt(skill_id=_SKILL_ID, playbook=playbook).text

    async def review(
        self,
        *,
        sections: dict[str, Any],
        source_profile: dict[str, Any] | None = None,
        role_family: str | None = None,
    ) -> ReviewerResult:
        if not settings.jc_llm_enabled:
            return ReviewerResult(
                status=ReviewerStatus.PENDING,
                notes="自动质检未启用，本次没有核对简历内容。",
                issues=[{"code": "llm_disabled", "message": "Reviewer requires LLM",
                         "severity": "warning"}],
                available=False,
            )

        if not source_profile:
            return ReviewerResult(
                status=ReviewerStatus.PENDING,
                notes="找不到对应的事实档案，自动质检本次没有核对简历内容。",
                issues=[{"code": "missing_source", "message": "Source profile required",
                         "severity": "warning"}],
                available=False,
            )
        # Facts are retained verbatim; binary/render-only photo data is not evidence.
        # Do not let a headshot fill the context or trigger the 100k input guard.
        sections = copy.deepcopy(sections)
        source_profile = copy.deepcopy(source_profile)
        source_profile.pop("meta", None)
        source_profile.pop("i18n", None)
        contact = source_profile.get("contact")
        if isinstance(contact, dict):
            contact.pop("photo", None)
        def strip_render_data(value: Any) -> None:
            if isinstance(value, dict):
                value.pop("photo_data_uri", None)
                value.pop("generation", None)
                for child in value.values():
                    strip_render_data(child)
            elif isinstance(value, list):
                for child in value:
                    strip_render_data(child)
        strip_render_data(sections)
        strip_render_data(source_profile)
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
        try:
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
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError):
            return ReviewerResult(
                status=ReviewerStatus.PENDING,
                notes="自动质检暂时无法读取简历内容，本次没有核对。",
                issues=[
                    {
                        "code": "review_input_unserializable",
                        "severity": "warning",
                        "message": "Review input not JSON-serializable",
                    }
                ],
                available=False,
            )
        if len(review_input) > 100_000:
            return ReviewerResult(
                status=ReviewerStatus.PENDING,
                notes="简历内容超过自动质检的处理上限，本次没有核对。",
                issues=[{"code": "input_too_large", "message": "Review input too large",
                         "severity": "warning"}],
                available=False,
            )

        router = get_llm_router()

        def validate(response: Any) -> dict[str, Any]:
            # The contract is checked inside the call so that a model answering
            # in the wrong shape costs one endpoint rather than the whole
            # review. Only after every endpoint has answered badly does this
            # become "no verdict" below.
            data = json.loads(router.content_from_response(response))
            if (
                not isinstance(data, dict)
                or data.get("status") not in {"passed", "failed"}
                or not isinstance(data.get("issues"), list)
                or not all(isinstance(issue, dict) for issue in data["issues"])
            ):
                raise ValueError("invalid review contract")
            return data

        # The whole review has a hard deadline. Keep individual attempts shorter
        # so a slow primary cannot consume the fallback models' entire budget.
        total_budget = getattr(settings, "jc_export_review_timeout_seconds", 90)
        chain_length = len(router.chain_for("flash")) if hasattr(router, "chain_for") else 3
        attempt_budget = min(getattr(settings, "jc_export_review_attempt_timeout_seconds", 25),
                             total_budget / (max(1, chain_length) + .5))
        started = time.monotonic()
        logger.info("reviewer_call started input_chars=%d attempt_budget=%s total_budget=%s",
                    len(review_input), attempt_budget, total_budget)
        try:
            # HTTP SDK timeouts alone do not bound fallback/retry/backoff time.
            # Keep a wall-clock deadline even when called outside export orchestration.
            async with asyncio.timeout(total_budget):
                data = await router.acompletion(
                    "flash",
                    log_context=llm_context("resume_reviewer"),
                    messages=[
                        {"role": "system", "content": self._compose_system_prompt(playbook)},
                        {
                            "role": "user",
                            "content": review_input,
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    timeout_seconds=attempt_budget,
                    response_validator=validate,
                )
        except Exception as exc:  # noqa: BLE001 — every failure mode is "no verdict"
            # Raised once the whole chain is exhausted, whether the endpoints were
            # unreachable or every one of them answered in a shape we cannot read.
            # Both leave the user in the same place: no verdict. Letting this
            # propagate returned a 500 to someone who was told to wait for a quality
            # check, with the download still locked and nothing to act on.
            logger.warning("reviewer_call failed error_type=%s elapsed_ms=%d", type(exc).__name__,
                           int((time.monotonic() - started) * 1000), exc_info=True)
            if isinstance(exc, TimeoutError):
                return ReviewerResult(
                    status=ReviewerStatus.PENDING,
                    notes="模型核对超时，本次未完成自动质检；可以重试或自行确认后下载。",
                    issues=[{"code": "reviewer_timeout", "severity": "warning",
                             "message": "模型核对超过等待时限，未产生质检结论。"}],
                    available=False,
                )
            if "invalid review contract" in str(exc):
                return self._unreadable("invalid_review", "Invalid review contract")
            return ReviewerResult(
                status=ReviewerStatus.PENDING,
                notes="自动质检服务暂时不可用，本次没有核对简历内容。",
                issues=[{"code": "reviewer_unavailable", "severity": "warning",
                         "message": f"Reviewer call failed: {type(exc).__name__}"}],
                available=False,
            )
        logger.info("reviewer_call completed elapsed_ms=%d", int((time.monotonic() - started) * 1000))
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
    def _unreadable(code: str, message: str) -> ReviewerResult:
        """The model answered, but not in a shape we can read.

        Indistinguishable from an outage as far as the draft is concerned: we have no
        verdict. Reported as unavailable rather than as a failure, because the user did
        not write a malformed response and cannot fix one.
        """
        return ReviewerResult(
            status=ReviewerStatus.PENDING,
            notes="自动质检返回的结果无法解析，本次没有核对简历内容。",
            issues=[{"code": code, "severity": "warning", "message": message}],
            available=False,
        )

    @staticmethod
    def _has_blocking_issue(issues: list[dict[str, Any]]) -> bool:
        for issue in issues:
            severity = str(issue.get("severity") or issue.get("code") or "error").strip().lower()
            if severity != "warning":
                return True
        return False
