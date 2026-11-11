"""后台任务进程入口（O §1、P §3.1）。独立进程，不在 API 进程里起循环。

用法：python -m companion.worker_jobs    （需要 COMPANION_DATABASE_URL 与 COMPANION_REDIS_URL）

两件事并行：
- 任务队列：确认过期、审计清理、回合后记忆写入、摘要重建、账号注销；未知 kind 置 dead，不静默丢弃；
- 提醒调度：每隔几秒认领到期提醒，发起主动回合（多个 worker 同时跑也只发一次）。

装配与 API 进程相同（同一个 build_platform），所以主动回合的角色、记忆、提示词与普通回合一致。
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime

from companion.adapters.store.sql.repositories import SqlConfirmationStore, SqlToolCallStore
from companion.app.account.purge import PURGE_JOB
from companion.app.jobs.handlers import (
    account_purge,
    audit_trim,
    confirmation_expire,
    memory_record,
    persona_update,
    session_resummarize,
    timeline_record,
)
from companion.app.jobs.worker import JobWorker
from companion.app.persona.updater import PERSONA_JOB
from companion.domain.history.summary import RESUMMARIZE_JOB, TIMELINE_RECORD_JOB

REMINDER_POLL_SEC = 5.0
log = logging.getLogger("companion.worker")


async def _reminder_loop(dispatcher, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await dispatcher.run_once(datetime.now(UTC))
        except Exception:  # noqa: BLE001 —— 调度失败不能让进程退出
            log.exception("reminder dispatch round failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=REMINDER_POLL_SEC)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    from companion.bootstrap.platform import MEMORY_RECORD_JOB, build_platform, default_prompts
    from companion.config import settings

    logging.basicConfig(level=os.environ.get("COMPANION_LOG_LEVEL", "INFO"))
    platform = build_platform(settings, prompts=default_prompts())
    await platform.astart()

    handlers = {
        "confirmation.expire": confirmation_expire(SqlConfirmationStore(platform.engine)),
        "audit.trim": audit_trim(SqlToolCallStore(platform.engine)),
    }
    if platform.pipeline is not None:
        handlers[MEMORY_RECORD_JOB] = memory_record(platform.pipeline, sessions=platform.sessions)
    if platform.resummarize is not None:
        handlers[RESUMMARIZE_JOB] = session_resummarize(platform.resummarize)
    if platform.timeline_recorder is not None:
        handlers[TIMELINE_RECORD_JOB] = timeline_record(platform.timeline_recorder, sessions=platform.sessions)
    if platform.persona_updater is not None:
        handlers[PERSONA_JOB] = persona_update(platform.persona_updater, sessions=platform.sessions)
    if platform.account is not None:
        handlers[PURGE_JOB] = account_purge(platform.account)

    owner = f"{socket.gethostname()}:{os.getpid()}"
    worker = JobWorker(store=platform.jobs, handlers=handlers, owner=owner)
    stop = asyncio.Event()
    reminders = asyncio.create_task(_reminder_loop(platform.dispatcher, stop)) if platform.dispatcher else None
    try:
        await worker.run_forever()
    finally:
        stop.set()
        if reminders is not None:
            await reminders
        await platform.aclose()


if __name__ == "__main__":
    asyncio.run(main())
