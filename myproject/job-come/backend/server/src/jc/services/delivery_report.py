"""Deterministic defects appended to a reviewer's findings before delivery.

Three questions a model is not asked and does not need to be asked:

- **Is anything on the page unsupported by the profile?** (`with_invariant_issues`)
- **What *is* this file — did the writer actually run?** (`with_delivery_issues`)
- **Does the document hold together as a document?** (`with_structure_issues`)

These moved out of `ResumeService` because they are one concept — "what to tell the
user about this draft before they send it to an employer" — and none of them touch the
database, the session, or any service state. Keeping them beside `preview`/`export`
made the service the place every new kind of finding would land, which is how a file
reaches 1500 lines.

Two invariants hold across all three, and they are the reason this is a separate
module rather than three unrelated helpers:

1. **Everything is `warning`, never blocking.** A deterministic rule fires on
   legitimate writing often enough that making one a gate locks users out of their own
   document — a failure already fixed once in `ResumeReviewer._has_blocking_issue`.
   These change what the user is *told*, never what they are *allowed to do*.
2. **Nothing is reported twice.** Each function deduplicates against findings already
   present, so the reviewer saying something about a field means the deterministic
   check stays quiet about the same field.
"""

from __future__ import annotations

from typing import Any

from jc.schemas.profile_payload import ProfilePayload
from jc.services.resume_blueprint import evaluate_blueprint
from jc.services.resume_structure import audit_structure
from jc.services.writing_invariants import audit_additions

#: Placeholders the deterministic builder writes into a block with no source
#: highlights. They are ours, not the model's, so they never reach the reviewer's
#: "placeholder text" rule — which reads the draft as if a model wrote all of it.
PENDING_PLACEHOLDERS = ("（待补充经历要点）", "(Add experience highlights)")


def _fields_already_reported(issues: list[dict[str, Any]]) -> set[str]:
    return {
        str(issue.get("field") or "").strip()
        for issue in issues
        if str(issue.get("field") or "").strip()
    }


def with_invariant_issues(
    issues: list[dict[str, Any]],
    sections: dict[str, Any],
    source_profile: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Append deterministic unsupported-content findings the reviewer did not raise.

    The reviewer is the gate, and it reads intent in a way arithmetic cannot. But it
    is a model call, so "fabrication is caught" has been an assumption about model
    behaviour with nothing behind it. `writing_invariants` can prove a narrower claim
    without a model: this number, this ownership verb, appears nowhere in the profile.
    """
    if not source_profile:
        return list(issues)
    try:
        payload = ProfilePayload.model_validate(source_profile)
    except Exception:  # noqa: BLE001 — a malformed payload is the reviewer's problem
        return list(issues)

    already = _fields_already_reported(issues)
    out = list(issues)
    from jc.domain.claim_constraints import retracted_claim_findings

    for finding in retracted_claim_findings(sections, payload):
        if not any(
            i.get("code") == finding["code"] and i.get("field") == finding["field"]
            for i in out
        ):
            out.append({"severity": "warning", **finding})
    for finding in audit_additions(sections, payload).fabrications:
        if finding.field_path in already:
            continue
        out.append(
            {
                "severity": "warning",
                "code": f"invariant_{finding.kind}",
                "field": finding.field_path,
                "message": f"{finding.detail}如果确实发生过，把它补进档案再重新生成。",
            }
        )
    return out


def with_delivery_issues(
    issues: list[dict[str, Any]],
    sections: dict[str, Any],
) -> list[dict[str, Any]]:
    """Report what this file *is* before the user sends it to an employer.

    Two defects neither the reviewer nor the structure audit can see, because both
    read the draft as a document rather than asking how it was produced:

    1. **The AI writer never ran.** `generation.mode == "source_layout"` means the
       writer chain failed and the document is the profile's own wording, laid out.
       The preview panel says so; the export screen did not read the field at all,
       so a failed optimization downloaded under the same filename as a successful
       one. That is what makes "优化效果不好" indistinguishable from "优化没有发生".
    2. **A placeholder is on the page.** `（待补充经历要点）` is written by our own
       builder for a role with no highlights, so the reviewer's placeholder rule
       never sees it as model output. Shipping it to an employer is strictly worse
       than shipping a shorter resume.
    """
    out = list(issues)
    generation = sections.get("generation")
    mode = (generation or {}).get("mode") if isinstance(generation, dict) else None
    if mode in {"source_layout", "structure_guarded"}:
        known = {str(i.get("code") or "") for i in out}
        if "generation_not_optimized" not in known:
            out.append(
                {
                    "severity": "warning",
                    "code": "generation_not_optimized",
                    "field": "generation.mode",
                    "message": (
                        str((generation or {}).get("warning") or "").strip()
                        or "AI 写作未完成，当前内容按档案原文排版。"
                    )
                    + "导出前建议回到优化预览点「重新生成」。",
                }
            )
    for key, label in (("experience_blocks", "经历"), ("project_blocks", "项目")):
        for index, block in enumerate(sections.get(key) or []):
            if not isinstance(block, dict):
                continue
            for b_index, bullet in enumerate(block.get("bullets") or []):
                if not isinstance(bullet, str):
                    continue
                if bullet.strip() not in PENDING_PLACEHOLDERS:
                    continue
                out.append(
                    {
                        "severity": "warning",
                        "code": "placeholder_bullet",
                        "field": f"{key}[{index}].bullets[{b_index}]",
                        "message": (
                            f"这段{label}还是占位文字「{bullet.strip()}」，会原样印进导出文件。"
                            "请补充这段经历的要点，或在档案里删掉这段经历。"
                        ),
                    }
                )
    return out


def with_structure_issues(
    issues: list[dict[str, Any]],
    sections: dict[str, Any],
    role_family: str | None,
) -> list[dict[str, Any]]:
    """Append document-level defects the reviewer is not asked to judge.

    The reviewer reads for honesty and sentence quality. Structure — a missing scope
    line, a role whose first bullet is its weakest, a summary that never states a
    conclusion — is measurable without a model, and these are exactly the defects
    that make a factually perfect resume fail a screen.
    """
    already = _fields_already_reported(issues)
    out = list(issues)
    for item in audit_structure(sections, role_family=role_family).issues:
        if item.field_path in already:
            continue
        already.add(item.field_path)
        out.append(
            {
                "severity": "warning",
                "code": f"structure_{item.code}",
                "field": item.field_path,
                "message": item.message,
            }
        )
    # Unmet blueprint requirements last: they are the broadest statements ("分量与
    # 经历不相称") and would otherwise bury the specific findings above them.
    # Deduplicated by code rather than field, because several requirements legitimately
    # point at the same field while saying different things about it.
    seen_codes = {str(i.get("code") or "") for i in out}
    for item in evaluate_blueprint(sections, role_family=role_family).unmet_issues():
        if item["code"] in seen_codes:
            continue
        seen_codes.add(item["code"])
        out.append(item)
    return out
