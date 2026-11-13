"""加载系统角色目录。Python 不依赖 Java 仓库。

现在的主格式是「一个角色一个 md 文件」（见 ``catalog_md``）：283 个角色不再挤在一个大 JSON 里，
加角色是一个新文件、改角色只 diff 那一个文件。旧的 catalog.json + catalog-zh.json 仍可读，
只在目录里没有 roles/ 子目录时回退，供老部署和未迁移的副本使用。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from companion.service.roles.catalog_md import ROLES_DIR, load_catalog_from_files
from companion.agent.roles.catalog import RoleIndex, parse_catalog


def load_system_catalog(root: Path, *, reserved_ids: Iterable[str] = ()) -> RoleIndex:
    if (root / ROLES_DIR).is_dir():
        return load_catalog_from_files(root, reserved_ids=reserved_ids)
    source = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    overlay_path = root / "catalog-zh.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8")) if overlay_path.is_file() else None
    return parse_catalog(source, overlay, reserved_ids=reserved_ids)
