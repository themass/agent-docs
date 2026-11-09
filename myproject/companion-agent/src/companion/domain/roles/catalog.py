"""系统角色目录（D §5、P §4）。纯逻辑：解析、校验、索引、语言回退。无 I/O。

校验失败一律拒绝加载（启动期 fail-closed）：id 冲突、命名空间违规（系统 id 以 u_ 开头）、
与内置人设 id 冲突、分类引用不存在、提示词为空。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

SUPPORTED_LOCALES = ("zh-CN", "en", "ar")
DEFAULT_LOCALE = "zh-CN"
RTL_LOCALES = frozenset({"ar"})
USER_ROLE_PREFIX = "u_"
ROLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
MAX_PROMPT_CHARS = 4000  # 自建角色提示词上限；系统角色的提示词由 P §6.1 的角色层预算截断


class CatalogError(ValueError):
    """目录数据不合法。加载时抛出，进程拒绝启动。"""


@dataclass(frozen=True)
class Division:
    id: str
    label: str
    icon: str
    color: str
    label_zh: str | None = None


@dataclass(frozen=True)
class SystemRole:
    id: str
    division: str
    name: str
    description: str
    vibe: str
    emoji: str
    color: str
    featured: bool
    prompt: str
    name_zh: str | None = None
    description_zh: str | None = None
    vibe_zh: str | None = None


@dataclass(frozen=True)
class Display:
    name: str
    description: str
    vibe: str
    locale: str
    dir: str
    machine_translated: bool


def negotiate_locale(explicit: str | None, accept_language: str | None) -> str:
    """显式 locale 参数优先，其次 Accept-Language（按 q 值排序），最后默认 zh-CN（D §5.2）。"""
    if explicit:
        match = _match_locale(explicit)
        if match:
            return match
    if accept_language:
        ranked: list[tuple[float, str]] = []
        for part in accept_language.split(","):
            tag, _, params = part.strip().partition(";")
            q = 1.0
            if params.strip().startswith("q="):
                try:
                    q = float(params.strip()[2:])
                except ValueError:
                    q = 0.0
            ranked.append((q, tag))
        for _q, tag in sorted(ranked, key=lambda item: -item[0]):
            match = _match_locale(tag)
            if match:
                return match
    return DEFAULT_LOCALE


def _match_locale(tag: str) -> str | None:
    lowered = tag.strip().lower().replace("_", "-")
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en"
    if lowered.startswith("ar"):
        return "ar"
    return None


class RoleIndex:
    def __init__(self, divisions: Iterable[Division], roles: Iterable[SystemRole]) -> None:
        self._divisions = tuple(divisions)
        self._roles = tuple(sorted(roles, key=lambda r: r.id))
        self._by_id = {r.id: r for r in self._roles}
        self._division_by_id = {d.id: d for d in self._divisions}

    @property
    def divisions(self) -> tuple[Division, ...]:
        return self._divisions

    @property
    def roles(self) -> tuple[SystemRole, ...]:
        return self._roles

    def get(self, role_id: str) -> SystemRole | None:
        return self._by_id.get(role_id)

    def division_count(self, division_id: str) -> int:
        return sum(1 for r in self._roles if r.division == division_id)

    def search(self, *, division: str | None = None, q: str | None = None,
               featured: bool = False) -> list[SystemRole]:
        needle = q.strip().lower() if q else ""
        out = []
        for role in self._roles:
            if division and role.division != division:
                continue
            if featured and not role.featured:
                continue
            if needle and needle not in f"{role.name} {role.id} {role.description}".lower():
                continue
            out.append(role)
        return out

    def display(self, role: SystemRole, locale: str) -> Display:
        """展示字段按语言取值，缺失回退英文（D §5.2）。阿拉伯语暂用英文占位并标记机翻。"""
        direction = "rtl" if locale in RTL_LOCALES else "ltr"
        if locale == "zh-CN":
            return Display(role.name_zh or role.name, role.description_zh or role.description,
                           role.vibe_zh or role.vibe, locale, direction, machine_translated=False)
        if locale == "ar":
            # 没有 catalog-ar.json：英文占位，且明确标记，不编造翻译（T7 注意事项）。
            return Display(role.name, role.description, role.vibe, locale, direction, machine_translated=True)
        return Display(role.name, role.description, role.vibe, "en", "ltr", machine_translated=False)

    def division_label(self, division: Division, locale: str) -> str:
        if locale == "zh-CN" and division.label_zh:
            return division.label_zh
        return division.label


def parse_catalog(source: dict[str, Any], overlay: dict[str, Any] | None,
                  *, reserved_ids: Iterable[str] = ()) -> RoleIndex:
    if not isinstance(source, dict) or not isinstance(source.get("roles"), list):
        raise CatalogError("catalog must contain a roles list")
    raw_divisions = source.get("divisions") or []
    divisions = []
    for item in raw_divisions:
        divisions.append(Division(
            id=_str(item, "id"), label=_str(item, "label"), icon=str(item.get("icon", "")),
            color=str(item.get("color", ""))))
    division_ids = {d.id for d in divisions}
    if len(division_ids) != len(divisions):
        raise CatalogError("duplicate division id")

    overlay = overlay or {}
    zh_roles = overlay.get("roles") or {}
    zh_divisions = overlay.get("divisions") or {}
    divisions = [
        Division(d.id, d.label, d.icon, d.color, label_zh=zh_divisions.get(d.id)) for d in divisions
    ]

    reserved = set(reserved_ids)
    roles: list[SystemRole] = []
    seen: set[str] = set()
    for item in source["roles"]:
        role_id = _str(item, "id")
        if not ROLE_ID_PATTERN.match(role_id):
            raise CatalogError(f"invalid role id {role_id!r}")
        if role_id.startswith(USER_ROLE_PREFIX):
            raise CatalogError(f"system role id must not use the {USER_ROLE_PREFIX!r} namespace: {role_id}")
        if role_id in seen:
            raise CatalogError(f"duplicate role id {role_id}")
        if role_id in reserved:
            raise CatalogError(f"role id collides with a builtin persona: {role_id}")
        seen.add(role_id)
        division = _str(item, "division")
        if division not in division_ids:
            raise CatalogError(f"role {role_id} references unknown division {division}")
        prompt = _str(item, "prompt")
        zh = zh_roles.get(role_id) or {}
        roles.append(SystemRole(
            id=role_id, division=division, name=_str(item, "name"),
            description=str(item.get("description", "")), vibe=str(item.get("vibe", "")),
            emoji=str(item.get("emoji", "")), color=str(item.get("color", "")),
            featured=bool(item.get("featured", False)), prompt=prompt,
            name_zh=zh.get("name"), description_zh=zh.get("description"), vibe_zh=zh.get("vibe"),
        ))

    unknown_overlay = set(zh_roles) - seen
    if unknown_overlay:
        raise CatalogError(f"overlay references unknown role ids: {sorted(unknown_overlay)[:5]}")
    return RoleIndex(divisions, roles)


def _str(item: Any, key: str) -> str:
    value = item.get(key) if isinstance(item, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"missing or empty field {key!r}")
    return value
