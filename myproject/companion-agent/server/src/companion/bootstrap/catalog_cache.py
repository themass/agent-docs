"""进程级系统角色目录缓存（stage-6）。

2026-11-23 真机：prewarm 已盖住重 import，但每间房仍在事件循环里同步
`build_platform` → `load_system_catalog`（283×md+yaml，loop_monitor 样本帧 pathlib
10s+）。目录在 worker 生命周期内不变，应在 job 进程 prewarm 时加载一次并复用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from companion.paths import ROLES_CATALOG_DIR
from companion.service.roles.catalog_files import load_system_catalog

if TYPE_CHECKING:
    from companion.agent.roles.catalog import RoleIndex

_CATALOG: RoleIndex | None = None

# 与 platform.build_platform 一致；延迟导入 platform 避免循环依赖。
_RESERVED_IDS = ("linche", "sudai")


def warm_system_catalog() -> RoleIndex:
    """在 prewarm 里调用：扫盘一次，后续 build_platform 不再读 283 个 md。"""
    global _CATALOG  # noqa: PLW0603
    if _CATALOG is None:
        _CATALOG = load_system_catalog(ROLES_CATALOG_DIR, reserved_ids=_RESERVED_IDS)
    return _CATALOG


def get_system_catalog() -> RoleIndex | None:
    return _CATALOG


def clear_system_catalog_cache_for_tests() -> None:
    global _CATALOG  # noqa: PLW0603
    _CATALOG = None
