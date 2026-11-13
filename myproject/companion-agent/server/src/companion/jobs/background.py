"""后台循环：任务队列、提醒调度、主动开口、每日整理。

原来这三件事只存在于独立的 ``worker_jobs`` 进程里。拆出去的理由是多 API 副本时不能每个都扫
（同一条提醒会发 N 次），代价是多一个必须记得部署的进程——不部署它，聊天照常，但记忆、提醒、
主动消息全部静默失效，任务堆在表里没有任何报错。

现在默认跟着 API 进程一起跑，只在**一个**进程上开启（``COMPANION_JOBS_IN_API=true``）。
多副本时只给一个副本打开，其余关掉；也可以继续用 ``python -m companion.worker_jobs`` 单独跑。

无论哪种方式，多进程并存都不会重复发：任务队列用 ``FOR UPDATE SKIP LOCKED`` 认领，主动开口用
Redis ``SET NX`` 抢占，每日整理按日期去重。
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime

from companion.history.summary import RESUMMARIZE_JOB, TIMELINE_RECORD_JOB

log = logging.getLogger("companion.background")

REMINDER_POLL_SEC = 5.0
INITIATIVE_POLL_SEC = 60.0
DAILY_CHECK_SEC = 3600.0
CLAIM_TTL_SEC = 24 * 3600
# 每轮主循环写一次心跳文件的时间间隔。status 据此判断“进程活着但在空转”。
HEARTBEAT_SEC = 30.0


def build_handlers(platform) -> dict:
    """任务队列的处理函数表。缺哪块能力就不注册对应的 kind（未知 kind 会被置 dead）。"""
    from companion.adapters.store.sql.repositories import SqlConfirmationStore, SqlToolCallStore
    from companion.app.account.purge import PURGE_JOB
    from companion.jobs.handlers import (
        QA_PURGE_JOB, account_purge, audit_trim, confirmation_expire, memory_record, persona_update, qa_purge,
        session_resummarize, timeline_record, timeline_sweep)
    from companion.persona.updater import PERSONA_JOB
    from companion.timeline.sweep import TIMELINE_SWEEP_JOB
    from companion.bootstrap.platform import MEMORY_RECORD_JOB

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
    return handlers


def build_initiative_loop(platform):
    """主动开口：扫时间线里快到的事 → 让她说一句 → 投递到收件箱。"""
    from companion.brain.platform_brain import PlatformBrain
    from companion.proactive.loop import InitiativeLoop
    from companion.proactive.router import ChannelRouter
    from companion.proactive.scheduler import InitiativeScheduler
    from companion.proactive.speaker import PlatformSpeaker
    from companion.proactive.models import Channel

    async def claim(key: str) -> bool:
        return bool(await platform.redis.set(f"ca:initiative:{key}", b"1", nx=True, ex=CLAIM_TTL_SEC))

    brain = PlatformBrain(submit=platform.chat.submit, control=platform.chat.control, role="system", kind="proactive")
    return InitiativeLoop(
        scheduler=InitiativeScheduler(timeline=platform.timeline, preferences_loader=platform.preferences.load,
                                      state_loader=platform.ledger.state_for),
        speak=PlatformSpeaker(sessions=platform.sessions, brain=brain, compliance=platform.compliance),
        router=ChannelRouter({Channel.IN_APP: platform.delivery}, recorder=platform.ledger),
        preferences_loader=platform.preferences.load,
        state_loader=platform.ledger.state_for,
        claim=claim,
    )


async def _every(stop: asyncio.Event, interval: float, work, name: str, heartbeat=None) -> None:
    """按间隔重复执行；单轮失败只记日志，不让循环退出。"""
    while not stop.is_set():
        try:
            await work()
            if heartbeat is not None:
                heartbeat()
        except Exception:  # noqa: BLE001
            log.exception("%s round failed", name)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


class BackgroundJobs:
    """后台循环的句柄。``start()`` 起协程，``stop()`` 收干净。"""

    def __init__(self, platform, *, heartbeat_path: str = "") -> None:
        self._platform = platform
        self._heartbeat_path = heartbeat_path
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._worker = None

    @property
    def running(self) -> bool:
        return any(not t.done() for t in self._tasks)

    def heartbeat(self) -> None:
        """写一次心跳时间戳。jobs 进程不监听端口，PID 活着不代表在干活，靠这个判断。"""
        if not self._heartbeat_path:
            return
        try:
            with open(self._heartbeat_path, "w") as f:      # noqa: PTH123 —— 一行写完，不需要原子替换
                f.write(datetime.now(UTC).isoformat())
        except OSError:
            log.warning("heartbeat write failed", extra={"path": self._heartbeat_path})

    async def start(self) -> None:
        from companion.jobs.worker import JobWorker

        platform = self._platform
        owner = f"{socket.gethostname()}:{os.getpid()}"
        self._worker = JobWorker(store=platform.jobs, handlers=build_handlers(platform), owner=owner)
        self.heartbeat()
        # 队列循环单独留在 self._queue 上：它是无限循环，只在独立进程模式下 await 它
        self._queue = asyncio.create_task(self._worker.run_forever(), name="job-queue")
        self._tasks = [self._queue]
        if platform.dispatcher is not None:
            self._tasks.append(asyncio.create_task(_every(
                self._stop, REMINDER_POLL_SEC,
                lambda: platform.dispatcher.run_once(datetime.now(UTC)), "reminder", self.heartbeat), name="reminders"))
        self._tasks.append(asyncio.create_task(
            _every(self._stop, DAILY_CHECK_SEC, lambda: self._schedule_daily(), "daily", self.heartbeat), name="daily"))
        self._tasks.append(asyncio.create_task(
            _every(self._stop, INITIATIVE_POLL_SEC, self._initiative_once, "initiative", self.heartbeat),
            name="initiative"))
        log.info("background jobs started (owner=%s, tasks=%d)", owner, len(self._tasks))

    async def _initiative_once(self) -> None:
        loop = getattr(self, "_initiative", None)
        if loop is None:
            loop = self._initiative = build_initiative_loop(self._platform)
        await loop.run_once()

    async def _schedule_daily(self) -> None:
        """入队今天的整理任务。按日期去重，多个进程同时入队也只有一条。"""
        from companion.jobs.handlers import QA_PURGE_JOB
        from companion.timeline.sweep import TIMELINE_SWEEP_JOB

        today = datetime.now(UTC).date().isoformat()
        now = datetime.now(UTC).replace(tzinfo=None)
        for kind in (TIMELINE_SWEEP_JOB, QA_PURGE_JOB):
            await self._platform.jobs.enqueue(kind=kind, payload={}, run_after=now, dedupe_key=f"{kind}:{today}")

    async def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []


async def run_forever(platform) -> None:
    """独立进程模式（``python -m companion.worker_jobs``）：起循环，一直跑到被取消。"""
    import contextlib

    jobs = BackgroundJobs(platform)
    await jobs.start()
    try:
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*jobs._tasks)    # noqa: SLF001 —— 独立模式下由这些任务决定进程何时退出
    finally:
        await jobs.stop()
