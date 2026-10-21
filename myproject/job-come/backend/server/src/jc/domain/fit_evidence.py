"""Verify model-cited evidence against the exact current candidate source.

This verifies citation existence, not whether the quoted fact proves a requirement.
Semantic match/importance remain model advice. Missing evidence means unknown, not inability.
"""

from __future__ import annotations

import re
from typing import Any

from jc.domain.claim_constraints import is_retracted_source
from jc.schemas.job import JDParseResult, RequirementEvidence
from jc.schemas.profile_payload import ProfilePayload


def evidence_sources(profile: ProfilePayload) -> dict[str, tuple[str, str | None]]:
    sources: dict[str, tuple[str, str | None]] = {}
    if profile.summary:
        sources["summary"] = (profile.summary, None)
    for key in ("experiences", "projects", "education", "skills", "evidence_answers"):
        for i, item in enumerate(getattr(profile, key)):
            data = item.model_dump(mode="json")
            entity_id = data.get("id")
            for field, value in data.items():
                if field in {"id", "confidence", "field_path", "question", "kind", "answered_at"}:
                    continue
                if isinstance(value, str):
                    sources[f"{key}[{i}].{field}"] = (value, entity_id)
                elif isinstance(value, list):
                    for j, text in enumerate(value):
                        if isinstance(text, str):
                            sources[f"{key}[{i}].{field}[{j}]"] = (text, entity_id)
    return {
        path: value
        for path, value in sources.items()
        if not is_retracted_source(
            value[0],
            profile,
            scope="experience"
            if path.startswith("experiences[")
            else ("project" if path.startswith("projects[") else "profile"),
            entity_id=value[1],
        )
    }


def verify_requirement_evidence(
    raw: list[dict[str, Any]],
    profile: ProfilePayload,
    jd: JDParseResult,
) -> list[RequirementEvidence]:
    sources = evidence_sources(profile)
    requirements = list(
        dict.fromkeys(
            jd.must_have_skills + jd.nice_to_have_skills + jd.requirements + jd.responsibilities
        )
    )
    by_requirement = {row.get("requirement"): row for row in raw if isinstance(row, dict)}
    out: list[RequirementEvidence] = []
    for requirement in requirements:
        row = RequirementEvidence.model_validate(
            by_requirement.get(requirement) or {"requirement": requirement}
        )
        verified = []
        for citation in row.evidence:
            source = sources.get(citation.field_path)
            if source and re.sub(r"\s+", "", citation.quote) == re.sub(r"\s+", "", source[0]):
                verified.append(citation.model_copy(update={"entity_id": source[1]}))
        invalid = len(verified) != len(row.evidence)
        # Citation existence is verified; semantic relevance remains model advice.
        out.append(
            row.model_copy(
                update={
                    "evidence": verified,
                    "status": row.status if verified and not invalid else "unverified",
                    "citation_status": "verified" if verified and not invalid else "unverified",
                    "importance": "unspecified"
                    if row.importance_basis == "estimated"
                    else row.importance,
                    "next_question": row.next_question
                    or ("目前材料尚未证明这项要求，请补充相关经历。" if not verified else None),
                }
            )
        )
    return out
