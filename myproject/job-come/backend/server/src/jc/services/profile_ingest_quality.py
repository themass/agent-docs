"""Heuristics for parsed profile payload quality."""

from __future__ import annotations

import re
from pathlib import Path

from jc.schemas.profile_payload import ProfilePayload


def humanize_filename(stem: str) -> str:
    text = re.sub(r"[_\-]+", " ", stem).strip()
    text = re.sub(r"\s+", " ", text)
    return text or ""


def payload_quality_score(payload: ProfilePayload, *, file_name: str) -> int:
    """Higher is better. 0 = unusable placeholder-like."""
    score = 0
    stem_name = humanize_filename(Path(file_name).stem)
    name = (payload.contact.name or "").strip()
    if name and name != stem_name and "待确认" not in name and len(name) <= 24:
        score += 20
    if payload.contact.email:
        score += 10
    if payload.contact.phone:
        score += 5
    if payload.summary and "解析草稿" not in (payload.summary or ""):
        score += 10
    for exp in payload.experiences:
        if exp.company and "待确认" not in exp.company:
            score += 15
        if exp.title and "待确认" not in exp.title:
            score += 10
        if exp.highlights:
            score += min(20, len(exp.highlights) * 5)
    for edu in payload.education:
        if edu.school and "待确认" not in edu.school:
            score += 8
    if payload.skills:
        score += min(10, len(payload.skills) * 2)
    return score


def is_low_quality_payload(payload: ProfilePayload, *, file_name: str) -> bool:
    return payload_quality_score(payload, file_name=file_name) < 35


def has_profile_facts(payload: ProfilePayload) -> bool:
    """Return true only when the model extracted at least one real source fact.

    Collection presence is not evidence: ``[{"company": "", ...}]`` and
    ``[{"name": ""}]`` are common empty model placeholders. IDs, dates,
    confidence and metadata are generated/structural fields and therefore do not
    make an otherwise empty extraction successful.
    """
    def text(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())
    if any(text(value) for value in (
        payload.contact.name, payload.contact.email, payload.contact.phone,
        payload.contact.location, payload.summary,
    )):
        return True
    if any(
        text(value)
        for item in payload.experiences
        for value in (item.company, item.title, item.start_date, item.end_date,
                      item.location, item.scope, *item.highlights, *item.skills)
    ):
        return True
    if any(
        text(value)
        for item in payload.education
        for value in (item.school, item.degree, item.major, item.start_date, item.end_date)
    ):
        return True
    if any(
        text(value)
        for item in payload.projects
        for value in (item.name, item.role, item.start_date, item.end_date,
                      item.description, item.scope, *item.highlights)
    ):
        return True
    return any(text(item.name) or any(text(e) for e in item.evidence) for item in payload.skills)
