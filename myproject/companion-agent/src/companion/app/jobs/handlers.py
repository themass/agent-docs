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


def memory_record(pipeline: Any, *, scope: str = "companion", clock: Callable[[], datetime] = utc_now):
    """回合后的记忆写入（chat-agent-memory-hooks.md §4.2）。任务按 turn_id 去重入队。"""
    from companion.domain.memory.hooks import TurnRecord

    async def handle(payload: dict[str, Any]) -> None:
        await pipeline.record(TurnRecord(
            scope=scope, user_id=str(payload["owner_id"]), turn_id=str(payload["turn_id"]),
            user_text=str(payload.get("user_text", "")), assistant_text=str(payload.get("assistant_text", "")),
            occurred_at=clock(), role_id=payload.get("role_id"), session_id=payload.get("session_id")))

    return handle


def session_resummarize(service: Any):
    """删除或编辑了已被摘要压缩的消息后，重建摘要。会话正忙时抛错，由任务退避重试。"""

    async def handle(payload: dict[str, Any]) -> None:
        await service.run(owner_id=int(payload["owner_id"]), session_id=int(payload["session_id"]))

    return handle
