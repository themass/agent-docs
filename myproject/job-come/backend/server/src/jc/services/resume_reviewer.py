"""The export review: what the reviewer reads, what its verdict says, and what that verdict blocks.

The reviewer is the `resume-reviewer` subtask. It is a run of its own (`jc.agent.subtask`) that
reads a draft with `jc_resume_review_read` and records one verdict per track with
`jc_resume_review_write`. The model call happens in that run; this module holds everything around
it that is a rule rather than a model call:

- which tracks a draft has and which role family each one is judged against,
- the input the reviewer is given, and when there is no honest input to give,
- the contract a verdict must meet to be read at all,
- which findings block an export. Only factual or integrity findings do. A reviewer that cannot
  reach a verdict is not a finding against the draft.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from jc.config import settings
from jc.domain.role_families import get_playbook, resolve_role_family
from jc.models.enums import ReviewerStatus
from jc.resume_locale import TRACK_BILINGUAL, normalize_track

#: The reviewer may not be given more than this many characters of draft and profile.
REVIEW_INPUT_LIMIT = 100_000

#: Keys of the verdict tracks a draft is reviewed in. Not locales: see resume_locale.TRACK_*.
REVIEW_MAIN = "main"
REVIEW_ZH = "zh"
REVIEW_EN = "en"

#: The role that reviews a draft, and the message that starts its run.
RESUME_REVIEWER_ROLE = "resume-reviewer"
REVIEW_MESSAGE = (
    "请核对简历草稿 draft_id={draft_id}：先用 jc_resume_review_read 读取各轨道，"
    "再用 jc_resume_review_write 一次性写入全部轨道的结论。不要改动简历内容。"
)

#: Set on a verdict dict when the reviewer produced no readable answer. Kept as a constant so the
#: write tool, the service and the tests agree on the code.
NO_VERDICT_CODE = "reviewer_no_verdict"


@dataclass(frozen=True, slots=True)
class ReviewerResult:
    status: ReviewerStatus
    notes: str | None
    issues: list[dict[str, Any]]
    # Did the reviewer actually reach a verdict about this draft?
    #
    # This is not the same question as `status`. "The reviewer read the draft and found an
    # unsupported number" and "the reviewer never answered" are different facts. The second must
    # never block a download: the user cannot fix a reviewer that did not run.
    available: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "notes": self.notes,
            "issues": self.issues,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewerResult:
        return cls(
            status=ReviewerStatus(data["status"]),
            notes=data.get("notes"),
            issues=list(data.get("issues") or []),
            available=bool(data.get("available", True)),
        )


def unavailable(code: str, message: str, notes: str) -> ReviewerResult:
    """No verdict: the reviewer did not run, answered in an unreadable shape, or ran out of time."""
    return ReviewerResult(
        status=ReviewerStatus.PENDING,
        notes=notes,
        issues=[{"code": code, "severity": "warning", "message": message}],
        available=False,
    )


def draft_role_family(sections: dict[str, Any], source_profile: dict[str, Any] | None) -> str:
    """The family a draft was written against: stamped on the draft, else the user's choice, else
    the profile's own titles. A bilingual wrapper carries no family of its own, so it is read from
    its tracks."""
    stamped = sections.get("role_family")
    if isinstance(stamped, str) and stamped.strip():
        return stamped.strip()
    if sections.get("track") == "bilingual":
        for key in ("zh_sections", "en_sections"):
            nested = sections.get(key)
            if isinstance(nested, dict):
                nested_family = nested.get("role_family")
                if isinstance(nested_family, str) and nested_family.strip():
                    return nested_family.strip()
    profile = source_profile or {}
    prefs = profile.get("preferences") if isinstance(profile, dict) else None
    override = prefs.get("role_family") if isinstance(prefs, dict) else None
    experiences = profile.get("experiences") if isinstance(profile, dict) else None
    titles: tuple[str | None, ...] = ()
    if isinstance(experiences, list):
        titles = tuple(exp.get("title") for exp in experiences[:2] if isinstance(exp, dict))
    return resolve_role_family(override=override, profile_titles=titles)


def track_role_family(track: dict[str, Any], fallback: str) -> str:
    """A track stamps its own family when it was written against one."""
    stamped = track.get("role_family")
    if isinstance(stamped, str) and stamped.strip():
        return stamped.strip()
    return fallback


def review_tracks(
    locale: str, sections: dict[str, Any], source_profile: dict[str, Any] | None
) -> dict[str, tuple[dict[str, Any], str]]:
    """Each track of a draft that needs a verdict, with the family it is judged against."""
    family = draft_role_family(sections, source_profile)
    if normalize_track(locale) == TRACK_BILINGUAL:
        zh = sections.get("zh_sections") or {}
        en = sections.get("en_sections") or {}
        return {
            REVIEW_ZH: (zh, track_role_family(zh, family)),
            REVIEW_EN: (en, track_role_family(en, family)),
        }
    return {REVIEW_MAIN: (sections, family)}


def build_review_input(
    sections: dict[str, Any],
    source_profile: dict[str, Any] | None,
    role_family: str,
) -> tuple[str | None, ReviewerResult | None]:
    """The JSON the reviewer reads for one track, or the reason there is no honest input to give.

    Returns `(text, None)` for a reviewable track and `(None, unavailable)` otherwise. An
    unavailable track never starts a reviewer run.
    """
    if not settings.jc_llm_enabled:
        return None, unavailable(
            "llm_disabled", "Reviewer requires LLM", "自动质检未启用，本次没有核对简历内容。"
        )
    if not source_profile:
        return None, unavailable(
            "missing_source", "Source profile required",
            "找不到对应的事实档案，自动质检本次没有核对简历内容。",
        )
    # Facts are retained verbatim; binary/render-only photo data is not evidence. A headshot must
    # not fill the context or trip the input limit.
    sections = copy.deepcopy(sections)
    source_profile = copy.deepcopy(source_profile)
    source_profile.pop("meta", None)
    source_profile.pop("i18n", None)
    contact = source_profile.get("contact")
    if isinstance(contact, dict):
        contact.pop("photo", None)
    _strip_render_data(sections)
    _strip_render_data(source_profile)
    # The playbook decides which warnings are legitimate for this audience. Without it the reviewer
    # applies engineering expectations to every role and tells a legal candidate a good bullet is
    # missing a metric.
    playbook = get_playbook(role_family or sections.get("role_family"))
    # The angles a draft was written from explain why a bullet leads with scale rather than result.
    # Without them the reviewer reports the user's own choice as a defect.
    emphases = sections.get("framing_emphases")
    if not isinstance(emphases, list):
        emphases = []
    try:
        text = json.dumps(
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
        return None, unavailable(
            "review_input_unserializable", "Review input not JSON-serializable",
            "自动质检暂时无法读取简历内容，本次没有核对。",
        )
    if len(text) > REVIEW_INPUT_LIMIT:
        return None, unavailable(
            "input_too_large", "Review input too large",
            "简历内容超过自动质检的处理上限，本次没有核对。"
        )
    return text, None


def _strip_render_data(value: Any) -> None:
    if isinstance(value, dict):
        value.pop("photo_data_uri", None)
        value.pop("generation", None)
        for child in value.values():
            _strip_render_data(child)
    elif isinstance(value, list):
        for child in value:
            _strip_render_data(child)


def verdict_result(verdict: Any) -> ReviewerResult:
    """A verdict written by the reviewer, read under its contract.

    The contract: `status` is `passed` or `failed`, `issues` is a list of finding objects, and
    `summary` is optional text. Anything else is unreadable, which is "no verdict", not a failure.
    """
    if (
        not isinstance(verdict, dict)
        or verdict.get("status") not in {"passed", "failed"}
        or not isinstance(verdict.get("issues"), list)
        or not all(isinstance(issue, dict) for issue in verdict["issues"])
    ):
        return unavailable(
            "invalid_review", "Invalid review contract",
            "自动质检返回的结果无法解析，本次没有核对简历内容。"
        )
    issues = list(verdict["issues"])
    summary = verdict.get("summary")
    status = ReviewerStatus.PASSED if verdict["status"] == "passed" else ReviewerStatus.FAILED
    # Only factual or integrity findings block export. Quality warnings are advice, so a reviewer
    # that reports them cannot lock the user out of their own document. An unrecognised severity
    # blocks (fail closed).
    if blocking_issues(issues):
        status = ReviewerStatus.FAILED
    return ReviewerResult(
        status=status,
        notes=summary if isinstance(summary, str) else None,
        issues=issues,
    )


def blocking_issues(issues: list[dict[str, Any]]) -> bool:
    for issue in issues:
        severity = str(issue.get("severity") or issue.get("code") or "error").strip().lower()
        if severity != "warning":
            return True
    return False


def aggregate_status(results: dict[str, ReviewerResult]) -> ReviewerStatus:
    """One status for a draft: failed if any track failed, passed only if every track passed."""
    statuses = {r.status for r in results.values()}
    if ReviewerStatus.FAILED in statuses:
        return ReviewerStatus.FAILED
    if statuses == {ReviewerStatus.PASSED}:
        return ReviewerStatus.PASSED
    return ReviewerStatus.PENDING
