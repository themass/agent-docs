"""已有依赖的任务处理函数（O §2.2）。其余任务待对应模块完成后注册（见 T10 报告）。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from companion.app.jobs.worker import utc_now
from companion.ports.store import ConfirmationStore
from companion.ports.tools import ToolCallStore

AUDIT_RETENTION = timedelta(days=90)


def confirmation_expire(store: ConfirmationStore, clock: Callable[[], datetime] = utc_now):
    """过期的待确认置 expired（条件更新，重复执行无副作用）。"""

    async def handle(payload: dict[str, Any]) -> None:
        await store.expire_due(now=clock())

    return handle


def audit_trim(audit_store: ToolCallStore, clock: Callable[[], datetime] = utc_now):
    """工具审计超过 90 天删除（O §2.2）。"""

    async def handle(payload: dict[str, Any]) -> None:
        await audit_store.trim_before(cutoff=clock() - AUDIT_RETENTION)

    return handle
