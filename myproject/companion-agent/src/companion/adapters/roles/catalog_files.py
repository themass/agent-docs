"""从本地 JSON 文件加载系统角色目录（T7）。Python 不依赖 Java 仓库。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from companion.domain.roles.catalog import RoleIndex, parse_catalog


def load_system_catalog(root: Path, *, reserved_ids: Iterable[str] = ()) -> RoleIndex:
    source = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    overlay_path = root / "catalog-zh.json"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8")) if overlay_path.is_file() else None
    return parse_catalog(source, overlay, reserved_ids=reserved_ids)
