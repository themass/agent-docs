"""Deterministic recurrence checks for user-confirmed, explicitly scoped corrections.

Exact normalized phrase matches only: no claim that paraphrases/translations are detected.
Stable source IDs are required; an absent ID never widens an entity rule to the profile.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from jc.schemas.profile_payload import ProfilePayload


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text)).casefold()


def retracted_claim_findings(
    sections: dict[str, Any], profile: ProfilePayload
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if sections.get("track") == "bilingual":
        for key in ("zh_sections", "en_sections"):
            findings.extend(
                {**item, "field": f"{key}.{item['field']}"}
                for item in retracted_claim_findings(sections.get(key) or {}, profile)
            )
        return findings
    candidates: list[tuple[str, str, str | None, str]] = []
    summary = sections.get("summary")
    if isinstance(summary, str):
        candidates.append(("summary", summary, None, "profile"))
    for key, scope in (("experience_blocks", "experience"), ("project_blocks", "project")):
        id_key = "experience_id" if scope == "experience" else "project_id"
        for i, block in enumerate(sections.get(key) or []):
            if not isinstance(block, dict):
                continue
            entity = block.get("id") or block.get(id_key)
            for field in ("scope", "scope_line", "description", "title", "role", "company", "name"):
                if isinstance(block.get(field), str):
                    candidates.append((f"{key}[{i}].{field}", block[field], entity, scope))
            for j, text in enumerate(block.get("bullets") or []):
                if isinstance(text, str):
                    candidates.append((f"{key}[{i}].bullets[{j}]", text, entity, scope))
    for rule in profile.constraints.retracted_claims:
        for path, text, entity, scope in candidates:
            if rule.scope != "profile" and (rule.scope != scope or rule.entity_id != entity):
                continue
            if _normalize(rule.claim) in _normalize(text):
                findings.append(
                    {
                        "code": "retracted_claim",
                        "field": path,
                        "message": (
                            f"出现用户已否认的表述：{rule.claim}。正确说法：{rule.correction}"
                        ),
                    }
                )
    return findings


def is_retracted_source(
    text: str, profile: ProfilePayload, *, scope: str, entity_id: str | None
) -> bool:
    """A denied phrase in an older source field must not be re-used as positive evidence."""
    return any(
        (rule.scope == "profile" or (rule.scope == scope and rule.entity_id == entity_id))
        and _normalize(rule.claim) in _normalize(text)
        for rule in profile.constraints.retracted_claims
    )
