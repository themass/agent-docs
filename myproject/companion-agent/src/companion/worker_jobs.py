"""后台任务进程入口（O §1、P §3.1）。独立进程，不在 API 进程里起循环。

用法：python -m companion.worker_jobs    （需要 COMPANION_DATABASE_URL 与 COMPANION_REDIS_URL）

两件事并行：
- 任务队列：确认过期、审计清理、回合后记忆写入、摘要重建、账号注销；未知 kind 置 dead，不静默丢弃；
- 提醒调度：每隔几秒认领到期提醒，发起主动回合（多个 worker 同时跑也只发一次）；
- 主动开口：每分钟扫时间线里快到的事，让她说一句并投递到收件箱（Redis 抢占，多个进程也只发一次）。

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
    qa_purge,
    session_resummarize,
    timeline_record,
    timeline_sweep,
)
from companion.app.jobs.handlers import QA_PURGE_JOB
from companion.app.jobs.worker import JobWorker
from companion.app.persona.updater import PERSONA_JOB
from companion.app.timeline.sweep import TIMELINE_SWEEP_JOB
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


INITIATIVE_POLL_SEC = 60.0
CLAIM_TTL_SEC = 24 * 3600


def build_initiative_loop(platform):
    """主动开口：扫时间线里快到的事 → 让她说一句 → 投递到收件箱。

    全部用平台里的 Postgres 存储（偏好、收件箱、频控账本、时间线），说的话经回合引擎落进会话历史。
    """
    from companion.app.proactive.loop import InitiativeLoop
    from companion.app.proactive.router import ChannelRouter
    from companion.app.proactive.scheduler import InitiativeScheduler
    from companion.app.proactive.speaker import PlatformSpeaker
    from companion.domain.proactive.models import Channel

    async def claim(key: str) -> bool:
        # SET NX：同一次发生只有一个后台进程抢得到；过期时间远长于扫描窗口
        return bool(await platform.redis.set(f"ca:initiative:{key}", b"1", nx=True, ex=CLAIM_TTL_SEC))

    from companion.adapters.brain.platform_brain import PlatformBrain

    brain = PlatformBrain(submit=platform.chat.submit, control=platform.chat.control, role="system", kind="proactive")
    speaker = PlatformSpeaker(sessions=platform.sessions, brain=brain, compliance=platform.compliance)
    return InitiativeLoop(
        scheduler=InitiativeScheduler(timeline=platform.timeline, preferences_loader=platform.preferences.load,
                                      state_loader=platform.ledger.state_for),
        speak=speaker,
        router=ChannelRouter({Channel.IN_APP: platform.delivery}, recorder=platform.ledger),
        preferences_loader=platform.preferences.load,
        state_loader=platform.ledger.state_for,
        claim=claim,
    )


async def _initiative_loop(loop, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await loop.run_once()
        except Exception:  # noqa: BLE001 —— 一轮失败不能让后台进程退出
            log.exception("initiative round failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=INITIATIVE_POLL_SEC)
        except asyncio.TimeoutError:
            pass


DAILY_CHECK_SEC = 3600.0


async def _schedule_daily(platform) -> None:
    """入队今天的整理任务：按日期去重，多个 worker 同时入队也只有一条。"""
    from companion.app.jobs.handlers import QA_PURGE_JOB
    from companion.app.timeline.sweep import TIMELINE_SWEEP_JOB

    today = datetime.now(UTC).date().isoformat()
    now = datetime.now(UTC).replace(tzinfo=None)
    for kind in (TIMELINE_SWEEP_JOB, QA_PURGE_JOB):
        await platform.jobs.enqueue(kind=kind, payload={}, run_after=now, dedupe_key=f"{kind}:{today}")


async def _daily_loop(platform, stop: asyncio.Event) -> None:
    """每小时看一眼今天的整理任务入队没有。worker 连续跑几天也会在日期变了之后补上；
    入队已存在时是空操作，所以检查得勤也不产生额外任务。不需要单独的定时器进程。"""
    while not stop.is_set():
        try:
            await _schedule_daily(platform)
        except Exception:  # noqa: BLE001 —— 入队失败下个小时再试，不能让 worker 退出
            log.exception("daily schedule failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=DAILY_CHECK_SEC)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    from companion.bootstrap.platform import MEMORY_RECORD_JOB, build_platform, default_prompts
    from companion.config import settings

    logging.basicConfig(level=os.environ.get("COMPANION_LOG_LEVEL", "INFO"))
    platform = build_platform(settings, prompts=default_prompts(), profile="jobs")
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
    if platform.timeline is not None:
        handlers[TIMELINE_SWEEP_JOB] = timeline_sweep(platform.timeline)
    if platform.persona_updater is not None:
        handlers[PERSONA_JOB] = persona_update(platform.persona_updater, sessions=platform.sessions)
    if platform.account is not None:
        handlers[PURGE_JOB] = account_purge(platform.account)
    if platform.qa is not None:
        handlers[QA_PURGE_JOB] = qa_purge(platform.qa, retention_days=platform.qa_retention_days,
                                          objects=platform.objects)

    owner = f"{socket.gethostname()}:{os.getpid()}"
    worker = JobWorker(store=platform.jobs, handlers=handlers, owner=owner)
    stop = asyncio.Event()
    reminders = asyncio.create_task(_reminder_loop(platform.dispatcher, stop)) if platform.dispatcher else None
    daily = asyncio.create_task(_daily_loop(platform, stop))
    initiative = asyncio.create_task(_initiative_loop(build_initiative_loop(platform), stop))
    try:
        await worker.run_forever()
    finally:
        stop.set()
        if reminders is not None:
            await reminders
        await daily
        await initiative
        await platform.aclose()


if __name__ == "__main__":
    asyncio.run(main())
