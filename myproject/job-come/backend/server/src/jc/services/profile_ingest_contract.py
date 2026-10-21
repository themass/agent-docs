"""Model-output anti-corruption boundary shared by all resume ingest strategies.

Only representation differences (null defaults/unknown text/server IDs) are
normalized. Facts, non-null wrong types and malformed JSON are never repaired.
"""
from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from typing import Any

from agentkit.common.ids import new_id
from pydantic import ValidationError

from jc.schemas.profile_payload import ProfilePayload
from jc.services.profile_ingest_quality import has_profile_facts

logger = logging.getLogger(__name__)
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.IGNORECASE | re.DOTALL)


class ProfileStructureError(RuntimeError):
    """Only stable, PII-free reason codes may be exposed to callers."""


def parse_profile_json(content: str) -> dict[str, Any]:
    """Parse one JSON object, tolerating a model's accidental Markdown fence.

    Do not include response content in error messages: resumes can contain personal data and
    errors are persisted in ingest logs.
    """
    text = content.strip()
    if not text:
        raise ProfileStructureError("empty_model_response")

    fenced = _CODE_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    if not text:
        raise ProfileStructureError("empty_model_response")

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProfileStructureError("invalid_json_response") from exc
    if not isinstance(value, dict):
        raise ProfileStructureError("invalid_json_object")
    return value


def normalize_model_profile(data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    # These containers already have empty defaults in ProfilePayload.
    for field in ("contact", "meta", "preferences", "constraints"):
        if result.get(field) is None:
            result[field] = {}
    for field in ("experiences", "education", "projects", "skills"):
        if result.get(field) is None:
            result[field] = []
    contact = result.get("contact")
    if isinstance(contact, dict) and contact.get("links") is None:
        contact["links"] = []
    for collection, prefix, fields, lists in (
        ("experiences", "exp", ("company", "title", "start_date"), ("highlights", "skills")),
        ("education", "edu", ("school",), ()),
        ("projects", "prj", ("name",), ("highlights",)),
    ):
        entries = result.get(collection)
        if not isinstance(entries, list):
            continue
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("id")
            if identifier is None or (
                isinstance(identifier, str) and (not identifier.strip() or identifier in seen)
            ):
                entry["id"] = new_id(prefix)
            if isinstance(entry.get("id"), str):
                seen.add(entry["id"])
            unknown = False
            for field in fields:
                if entry.get(field) is None:
                    entry[field] = ""
                if entry.get(field) == "":
                    unknown = True
            if unknown:
                entry["confidence"] = "needs_review"
            for field in lists:
                if entry.get(field) is None:
                    entry[field] = []
    skills = result.get("skills")
    if isinstance(skills, list):
        for skill in skills:
            if isinstance(skill, dict) and skill.get("evidence") is None:
                skill["evidence"] = []
    return result


def validate_profile_content(content: str, *, source_file: str) -> ProfilePayload:
    data = normalize_model_profile(parse_profile_json(content))
    try:
        profile = ProfilePayload.model_validate(data)
    except ValidationError as exc:
        # No values, model text, or unexpected field names enter logs.
        logger.warning(
            "profile_ingest_contract rejected schema error_types=%s count=%d",
            sorted({e["type"] for e in exc.errors(include_input=False)}),
            exc.error_count(),
        )
        raise ProfileStructureError("invalid_profile_schema") from exc
    if not has_profile_facts(profile):
        raise ProfileStructureError("empty_profile_response")
    profile.meta.source_file = source_file
    return profile
