"""从「一个角色一个 md 文件」加载系统角色目录。

为什么不用一个大 JSON：283 个角色挤在 1.3MB 的 JSON 里，加角色要改巨型文件，
diff 看不出改了谁，提示词还得从字符串里解转义。拆成 md 之后一个角色一个文件，
提示词就是正文，中文覆盖与英文原文在同一个文件里，不会两边 id 漂移。

文件布局：``roles/catalog/roles/<division>/<id>.md``
frontmatter 存结构化字段与中文覆盖，正文是英文提示词；分类列表仍在 ``divisions.json``。

校验仍交给 ``domain.roles.catalog.parse_catalog``：重复 id、id 命名空间、未知分类、
空提示词都还是启动期 fail-closed，换存储格式不放松任何一条规则。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from companion.domain.roles.catalog import CatalogError, RoleIndex, parse_catalog

ROLES_DIR = "roles"
DIVISIONS_FILE = "divisions.json"
LEGACY_CATALOG = "catalog.json"


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise CatalogError(f"{path}: 缺少 frontmatter")
    _, _, rest = text.partition("---\n")
    front, sep, body = rest.partition("\n---")
    if not sep:
        raise CatalogError(f"{path}: frontmatter 没有闭合")
    try:
        meta = yaml.safe_load(front) or {}
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path}: frontmatter 不是合法 YAML: {exc}") from exc
    if not isinstance(meta, dict):
        raise CatalogError(f"{path}: frontmatter 必须是映射")
    return meta, body.strip()


def load_divisions(root: Path) -> list[dict[str, Any]]:
    """分类是少量稳定元数据，单独一个文件；老仓库只有 catalog.json 时从那里取。"""
    path = root / DIVISIONS_FILE
    if path.is_file():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return list(data.get("divisions") or [])
    legacy = root / LEGACY_CATALOG
    if legacy.is_file():
        import json

        return list(json.loads(legacy.read_text(encoding="utf-8")).get("divisions") or [])
    raise CatalogError(f"{root}: 找不到 {DIVISIONS_FILE} 或 {LEGACY_CATALOG}")


def load_role_files(root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """扫描 md 文件，返回 (英文源, 中文覆盖) 两块，形状与 parse_catalog 期望的一致。"""
    roles_dir = root / ROLES_DIR
    if not roles_dir.is_dir():
        raise CatalogError(f"{root}: 找不到角色目录 {ROLES_DIR}/")
    source: list[dict[str, Any]] = []
    overlay: dict[str, dict[str, Any]] = {}
    for path in sorted(roles_dir.rglob("*.md")):
        meta, prompt = _read_frontmatter(path)
        role_id = str(meta.get("id") or "").strip()
        if not role_id:
            raise CatalogError(f"{path}: frontmatter 缺少 id")
        if path.stem != role_id:
            # 文件名就是 id，改 id 必须改名，避免出现"文件名和 id 不一致"的隐性地雷
            raise CatalogError(f"{path}: 文件名 {path.stem!r} 与 id {role_id!r} 不一致")
        source.append({
            "id": role_id,
            "division": str(meta.get("division") or ""),
            "name": str(meta.get("name") or ""),
            "description": str(meta.get("description") or ""),
            "vibe": str(meta.get("vibe") or ""),
            "emoji": str(meta.get("emoji") or ""),
            "color": str(meta.get("color") or ""),
            "featured": bool(meta.get("featured", False)),
            "prompt": prompt,
        })
        zh = meta.get("zh")
        if isinstance(zh, dict) and zh:
            overlay[role_id] = {k: str(zh[k]) for k in ("name", "description", "vibe") if zh.get(k)}
    return source, overlay


def load_catalog_from_files(root: Path, *, reserved_ids: Any = ()) -> RoleIndex:
    divisions = load_divisions(root)
    roles, overlay = load_role_files(root)
    return parse_catalog(
        {"divisions": divisions, "roles": roles},
        {"roles": overlay},
        reserved_ids=reserved_ids,
    )
