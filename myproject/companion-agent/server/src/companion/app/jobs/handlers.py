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


def memory_record(pipeline: Any, *, scope: str = "companion", clock: Callable[[], datetime] = utc_now,
                  sessions: Any = None):
    """回合后的记忆写入（chat-agent-memory-hooks.md §4.2）。任务按 turn_id 去重入队。

    ``sessions``：给了就先确认会话还在。会话被删除或账号已注销时跳过，不把记忆写回来。
    """
    from companion.memory.hooks import TurnRecord

    async def handle(payload: dict[str, Any]) -> None:
        if sessions is not None and payload.get("session_id") is not None:
            if await sessions.get(owner_id=int(payload["owner_id"]), session_id=int(payload["session_id"])) is None:
                return
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


def timeline_sweep(store: Any):
    """每日整理时间线（过期的一次性事件置 missed）。任务本身与用户无关，没有载荷。"""
    from companion.timeline.sweep import sweep_overdue

    async def handle(payload: dict[str, Any]) -> None:
        await sweep_overdue(store)

    return handle


def persona_update(updater: Any, *, sessions: Any = None):
    """批量更新用户画像。会话已删除或账号已注销时跳过，不把画像写回来。"""

    async def handle(payload: dict[str, Any]) -> None:
        if sessions is not None and await sessions.get(
                owner_id=int(payload["owner_id"]), session_id=int(payload["session_id"])) is None:
            return
        await updater.run(owner_id=int(payload["owner_id"]), role_id=str(payload["role_id"]),
                          session_id=int(payload["session_id"]),
                          up_to_message_id=int(payload["up_to_message_id"]))

    return handle


def account_purge(service: Any):
    """账号注销的跨存储删除。每一步可重复执行，失败整体重试（chat-agent-ops-design.md §3）。"""

    async def handle(payload: dict[str, Any]) -> None:
        requested = payload.get("requested_at")
        await service.run(owner_id=int(payload["owner_id"]),
                          requested_at=datetime.fromisoformat(requested) if requested else None)

    return handle


def timeline_record(service: Any, *, sessions: Any = None):
    """回合后的事件抽取（chat-agent-timeline-design.md §5）。会话已删除或账号已注销时跳过。"""

    async def handle(payload: dict[str, Any]) -> None:
        if sessions is not None and payload.get("session_id") is not None:
            if await sessions.get(owner_id=int(payload["owner_id"]), session_id=int(payload["session_id"])) is None:
                return
        await service.record_turn(owner_id=int(payload["owner_id"]), role_id=str(payload.get("role_id", "")),
                                  session_id=payload.get("session_id"),
                                  user_message_id=int(payload["user_message_id"]),
                                  user_text=str(payload.get("user_text", "")),
                                  assistant_text=str(payload.get("assistant_text", "")))

    return handle


QA_PURGE_JOB = "qa.purge"


def qa_purge(store: Any, *, retention_days: int, objects: Any = None, clock: Callable[[], datetime] = utc_now):
    """质检数据超过保留期限删除；语音音频对象一并删除。

    对象删除失败只记日志、不让任务失败重试：表里的记录已经删了，再重试也找不到键，
    孤儿对象由对象存储自己的生命周期规则兜底。
    """
    import logging

    log = logging.getLogger("companion.qa")

    async def handle(payload: dict[str, Any]) -> None:
        purged = await store.purge_before(cutoff=clock() - timedelta(days=retention_days))
        if objects is not None:
            for key in purged.object_keys:
                try:
                    await objects.delete(key=key)
                except Exception:  # noqa: BLE001
                    log.warning("qa audio delete failed", extra={"key": key})
        log.info("qa purge finished", extra={"rows": purged.rows, "objects": len(purged.object_keys)})

    return handle
