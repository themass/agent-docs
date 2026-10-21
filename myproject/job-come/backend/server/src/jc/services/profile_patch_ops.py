"""Validated edits to profile content, independent of MCP/HTTP/confirmation storage.

Accept nested partial objects or explicit field paths. Never interpret a path as a
literal extra field: Pydantic's default extra-ignore would silently discard it.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from pydantic import ValidationError

from jc.exceptions import AppError
from jc.resume_locale import other_monolingual
from jc.schemas.profile_payload import ProfilePayload
from jc.services.profile_i18n import detect_profile_source_locale, project_i18n_pack

_PATH = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*(?:\[(?:0|[1-9][0-9]*)\]|\.[a-zA-Z_][a-zA-Z_0-9]*)*")
_EDITABLE = {
    "contact",
    "summary",
    "experiences",
    "education",
    "projects",
    "skills",
    "preferences",
    "constraints",
    "evidence_answers",
}


def _invalid(message: str) -> AppError:
    return AppError(message, code="invalid_profile_patch")


def _tokens(path: str) -> tuple[str | int, ...]:
    if not isinstance(path, str) or len(path) > 256 or not _PATH.fullmatch(path):
        raise _invalid("修改路径格式不正确，请基于档案字段重新生成修改。")
    return tuple(
        int(t) if t.isdigit() else t for t in re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+", path)
    )


def _merge(base: Any, value: Any) -> Any:
    if isinstance(base, dict) and isinstance(value, dict):
        out = copy.deepcopy(base)
        for key, item in value.items():
            out[key] = _merge(out.get(key), item)
        return out
    return copy.deepcopy(value)


def _assert_fields_survive(raw: Any, validated: Any) -> None:
    """Disallow unknown fields at any depth, including replaced list items."""
    if isinstance(raw, dict) and isinstance(validated, dict):
        for key, value in raw.items():
            if key not in validated:
                raise _invalid("修改包含不存在的档案字段，请读取最新档案后重新生成。")
            _assert_fields_survive(value, validated[key])
    elif isinstance(raw, list) and isinstance(validated, list):
        for left, right in zip(raw, validated, strict=True):
            _assert_fields_survive(left, right)


def apply_profile_patch(base: dict[str, Any], patch: dict[str, Any]) -> ProfilePayload:
    """Apply validated, non-overlapping edits without mutating the caller's data."""
    if not isinstance(patch, dict) or not patch:
        raise _invalid("修改内容不能为空。")
    before = ProfilePayload.model_validate(base).model_dump(mode="json")
    out = copy.deepcopy(before)
    paths = [_tokens(key) for key in patch]
    for index, ((_, value), path) in enumerate(zip(patch.items(), paths, strict=True)):
        if path[0] not in _EDITABLE:
            raise _invalid("该字段不能通过简历内容修改工具更改。")
        for other in paths[:index]:
            if path[: len(other)] == other or other[: len(path)] == path:
                raise _invalid("修改路径互相重叠，请只提交具体字段的修改。")
        node = out
        for part in path[:-1]:
            if isinstance(part, int):
                if not isinstance(node, list) or part >= len(node):
                    raise _invalid("修改目标的序号已不存在，请读取最新档案后重新生成。")
            elif not isinstance(node, dict) or part not in node:
                raise _invalid("修改目标不存在，请读取最新档案后重新生成。")
            node = node[part]
        last = path[-1]
        if isinstance(last, int):
            if not isinstance(node, list) or last >= len(node):
                raise _invalid("修改目标的序号已不存在，请读取最新档案后重新生成。")
        elif not isinstance(node, dict) or last not in node:
            raise _invalid("修改目标不存在，请读取最新档案后重新生成。")
        node[last] = _merge(node[last], value)
    try:
        payload = ProfilePayload.model_validate(out)
    except ValidationError as exc:
        raise _invalid("修改内容不符合档案结构，请基于最新档案重新生成。") from exc
    prior_rules = ProfilePayload.model_validate(before).constraints.retracted_claims
    for rule in payload.constraints.retracted_claims:
        # Existing rules remain attached to their IDs when a source entity is removed.
        # Newly proposed rules cannot refer to a typo/nonexistent source entity.
        if rule in prior_rules:
            continue
        entities = payload.experiences if rule.scope == "experience" else payload.projects
        if rule.scope != "profile" and rule.entity_id not in {item.id for item in entities}:
            raise _invalid("纠正约束指向的经历/项目不存在，请读取最新档案。")
    after = payload.model_dump(mode="json")
    _assert_fields_survive(out, after)
    if before == after:
        raise AppError(
            "修改内容与当前档案相同，没有需要保存的变化。", code="profile_patch_no_change"
        )
    # Source text is authoritative. A stale source-language pack must never mask an edit.
    source = detect_profile_source_locale(payload)
    payload.meta.source_locale = source
    payload.i18n[source] = project_i18n_pack(payload)
    payload.meta.i18n_status[source] = "ready"
    target = other_monolingual(source)
    if target in payload.i18n or payload.meta.i18n_status.get(target) == "ready":
        payload.meta.i18n_status[target] = "stale"
    return payload
