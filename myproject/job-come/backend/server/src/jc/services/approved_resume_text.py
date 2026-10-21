"""Protect confirmed source wording from a second, implicit writer rewrite.

Confirmations already are the durable write ledger; no new table/cache is needed.
Only values still equal to the applied proposal are protected. A later edit wins.
The result is a request-local projection, never a new authoritative profile copy.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jc.models.profile_patch_confirm import ProfilePatchConfirm
from jc.schemas.profile_payload import ProfilePayload


def _leaves(value: Any, path: tuple = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            parts = tuple(int(p) if p.isdigit() else p for p in
                          re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+", key))
            yield from _leaves(child, path + parts)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _leaves(child, path + (i,))
    else:
        yield path, value


def confirmed_fields(profile: ProfilePayload, patches: list[dict]) -> dict[str, list[str]]:
    """Map stable entity IDs to confirmed fields, including legacy path patches."""
    raw = profile.model_dump(mode="json")
    fields: dict[str, set[str]] = {}
    for patch in patches:
        for path, expected in _leaves(patch):
            try:
                current = raw
                for part in path:
                    current = current[part]
            except (KeyError, IndexError, TypeError):
                continue
            if current != expected:
                continue
            if path == ("summary",):
                fields.setdefault("summary", set()).add("summary")
            elif (len(path) >= 3 and path[0] in {"experiences", "projects"}
                  and isinstance(path[1], int)
                  and path[2] in {"highlights", "scope", "description"}):
                entity = raw[path[0]][path[1]]
                fields.setdefault(f"{path[0]}/{entity['id']}", set()).add(path[2])
    return {key: sorted(value) for key, value in fields.items()}


async def with_confirmed_fields(db: AsyncSession, profile_id: str,
                                profile: ProfilePayload) -> ProfilePayload:
    patches = (await db.scalars(select(ProfilePatchConfirm.patch).where(
        ProfilePatchConfirm.profile_id == profile_id,
        ProfilePatchConfirm.status == "applied",
    ))).all()
    result = profile.model_copy(deep=True)
    result.meta.approved_resume_fields = confirmed_fields(profile, list(patches))
    return result


def preserve_confirmed(sections: dict[str, Any], profile: ProfilePayload,
                       baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    """Use confirmed source text verbatim; never infer an entity by array position."""
    # A translation is not the confirmed source wording. Source-locale overlays are
    # rebuilt on every save; other locales are allowed to translate, not copy Chinese.
    from jc.services.profile_i18n import detect_profile_source_locale
    from jc.resume_locale import normalize_track

    if normalize_track(sections.get("locale", "zh-CN")) != detect_profile_source_locale(profile):
        return sections
    locks = profile.meta.approved_resume_fields
    if not locks:
        return sections
    out = copy.deepcopy(sections)
    if "summary" in locks:
        out["summary"] = profile.summary or ""
    for source_key, block_key in (("experiences", "experience_blocks"), ("projects", "project_blocks")):
        blocks = out.setdefault(block_key, [])
        for entity in getattr(profile, source_key):
            fields = locks.get(f"{source_key}/{entity.id}", [])
            if not fields:
                continue
            matches = [b for b in blocks if b.get("id") == entity.id]
            if not matches:
                # Some writer models omit source IDs. A unique name/company match
                # is safe; a reordered numeric position is not.
                identity = "company" if source_key == "experiences" else "name"
                matches = [b for b in blocks if b.get(identity) == getattr(entity, identity)]
            if len(matches) != 1:
                original = next((b for b in (baseline or {}).get(block_key, [])
                                 if b.get("id") == entity.id), None)
                if original is None:
                    continue
                blocks.append(copy.deepcopy(original))
                matches = [blocks[-1]]
            block = matches[0]
            block["id"] = entity.id
            for field in fields:
                target = {"highlights": "bullets", "scope": "scope_line", "description": "description"}[field]
                block[target] = copy.deepcopy(getattr(entity, field))
    return out
