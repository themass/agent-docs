"""Task-sized profile reads. Never silently truncate facts or cut serialized JSON."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from jc.schemas.profile_payload import ProfilePayload

_SECTIONS = {
    "contact",
    "summary",
    "experiences",
    "education",
    "projects",
    "skills",
    "constraints",
    "preferences",
    "evidence_answers",
}
_PATH = re.compile(r"([a-z_]+)(?:\[(\d+)\])?(?:\.([a-z_]+)(?:\[(\d+)\])?)?")


def material_profile(profile: ProfilePayload) -> dict[str, Any]:
    """Writing/scoring need career facts, not binary photos or duplicate translations."""
    data = profile.model_dump(mode="json", exclude={"meta", "i18n"})
    data.get("contact", {}).pop("photo", None)
    return data


def read_profile_section(
    payload: dict[str, Any],
    *,
    section: str,
    offset: int = 0,
    limit: int = 5,
    field_path: str | None = None,
    text_offset: int | None = None,
    text_limit: int = 4000,
) -> dict[str, Any]:
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("offset must be >= 0 and limit must be 1..20")
    if section not in _SECTIONS | {"overview"}:
        raise ValueError("Unsupported profile section")
    if field_path:
        match = _PATH.fullmatch(field_path)
        if len(field_path) > 256 or not match or match[1] != section or section not in _SECTIONS:
            raise ValueError("field_path must be a field inside the requested section")
        value: Any = payload.get(section)
        try:
            if match[2] is not None:
                value = value[int(match[2])]
            if match[3] is not None:
                value = value[match[3]]
            if match[4] is not None:
                value = value[int(match[4])]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Profile field does not exist; read the latest overview") from exc
        result = {"field_path": field_path, "data": copy.deepcopy(value), "complete": True}
    elif section == "overview":
        # Counts, not a partial career presented as the whole source of truth.
        result = {
            "data": {
                "name": (payload.get("contact") or {}).get("name"),
                "sections": {
                    key: {"count": len(value)}
                    if isinstance(value, list)
                    else {"available": bool(value)}
                    for key in sorted(_SECTIONS)
                    if (value := payload.get(key)) is not None
                },
            },
            "complete": False,
            "read_tool": "jc_profile_get",
        }
    else:
        value = copy.deepcopy(payload.get(section))
        if isinstance(value, list):
            end = offset + limit
            result = {
                "data": value[offset:end],
                "total": len(value),
                "offset": offset,
                "next_offset": end if end < len(value) else None,
                "complete": offset == 0 and end >= len(value),
            }
        else:
            result = {"data": value, "complete": True}
    if section == "overview":
        for key in ("experiences", "projects"):
            items = payload.get(key) or []
            if not items:
                continue
            headings = []
            for index, item in enumerate(items[offset : offset + limit], start=offset):
                if isinstance(item, dict):
                    label = " · ".join(
                        str(item.get(field) or "")
                        for field in (
                            ("company", "title") if key == "experiences" else ("name", "role")
                        )
                    ).strip(" ·")
                    headings.append(
                        {
                            "id": item.get("id"),
                            "path": f"{key}[{index}]",
                            "label_preview": label[:80],
                            "label_truncated": len(label) > 80,
                        }
                    )
            result["data"]["sections"][key].update(
                entries=headings,
                offset=offset,
                next_offset=offset + limit if offset + limit < len(items) else None,
            )
    if field_path and isinstance(result.get("data"), list):
        items = result["data"]
        end = offset + limit
        result.update(
            data=items[offset:end],
            total=len(items),
            offset=offset,
            next_offset=end if end < len(items) else None,
            complete=offset == 0 and end >= len(items),
        )
    if text_offset is not None:
        value = result.get("data")
        if (
            not field_path
            or not isinstance(value, str)
            or type(text_offset) is not int
            or text_offset < 0
            or type(text_limit) is not int
            or not 1 <= text_limit <= 4000
        ):
            raise ValueError(
                "Text paging requires a string field_path, offset >= 0 and limit 1..4000"
            )
        end = text_offset + text_limit
        result.update(
            data=value[text_offset:end],
            text_offset=text_offset,
            total_chars=len(value),
            next_text_offset=end if end < len(value) else None,
            complete=text_offset == 0 and end >= len(value),
        )
    if len(json.dumps(result, ensure_ascii=False)) > 6_000:
        raise ValueError(
            "Profile read exceeds 6000 characters; narrow field_path/reduce limit; "
            "for a long string use field_path and text_offset=0"
        )
    return {"section": section, **result}


def turn_profile_context(profile: ProfilePayload, *, focus_path: str | None = None) -> str:
    """Small per-turn index; a focus may include one complete, bounded source field."""
    payload = profile.model_dump(mode="json")
    context = read_profile_section(payload, section="overview")
    constraints = payload.get("constraints") or {}
    if len(json.dumps(constraints, ensure_ascii=False)) <= 2_000:
        context["constraints"] = constraints
    else:
        context["constraints_read_required"] = "constraints"
    if focus_path:
        section = focus_path.split("[", 1)[0].split(".", 1)[0]
        try:
            focus = read_profile_section(payload, section=section, field_path=focus_path)
            if len(json.dumps(focus, ensure_ascii=False)) <= 4_000:
                context["focus"] = focus
            else:
                context["focus_read_required"] = focus_path
        except ValueError:
            context["focus_read_required"] = focus_path
    if len(json.dumps(context, ensure_ascii=False)) > 6_000:
        context.pop("focus", None)
        context["focus_read_required"] = focus_path
    return json.dumps(context, ensure_ascii=False)
