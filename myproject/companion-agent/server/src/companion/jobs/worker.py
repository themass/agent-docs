"""任务执行循环（O §2.1）：认领 → 执行 → 完成或退避。

- 执行期间每 60 秒续租一次；续租失败说明租约已被别人拿走，本进程放弃结果（不写入）。
- 处理函数必须幂等（崩溃重领会让同一任务执行两次）。
- 未注册的 kind 直接置 dead：不静默丢弃，也不无限重试。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from companion.jobs.policy import LEASE, LEASE_RENEW_EVERY_SECONDS, after_failure
from companion.jobs.port import JobRecord, JobStore

log = logging.getLogger("companion.jobs")

Handler = Callable[[dict[str, Any]], Awaitable[None]]


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class JobWorker:
    def __init__(self, *, store: JobStore, handlers: dict[str, Handler], owner: str,
                 batch: int = 10, clock: Callable[[], datetime] = utc_now,
                 renew_every: float = LEASE_RENEW_EVERY_SECONDS) -> None:
        self._store = store
        self._handlers = dict(handlers)
        self._owner = owner
        self._batch = batch
        self._clock = clock
        self._renew_every = renew_every

    async def run_once(self) -> int:
        now = self._clock()
        jobs = await self._store.claim(owner=self._owner, now=now, lease_until=now + LEASE, limit=self._batch)
        for job in jobs:
            await self._run_job(job)
        return len(jobs)

    async def run_forever(self, idle_sleep: float = 5.0) -> None:
        while True:
            try:
                count = await self.run_once()
            except Exception:  # noqa: BLE001 — 认领失败（如数据库抖动）不让进程退出
                log.exception("job claim failed")
                count = 0
            if count == 0:
                await asyncio.sleep(idle_sleep)

    async def _run_job(self, job: JobRecord) -> None:
        handler = self._handlers.get(job.kind)
        if handler is None:
            await self._store.fail(job_id=job.id, owner=self._owner, status="dead", run_after=None,
                                   error=f"unknown job kind: {job.kind}")
            log.error("unknown job kind", extra={"kind": job.kind})
            return
        renewer = asyncio.create_task(self._renew(job))
        try:
            await handler(job.payload)
        except Exception as exc:  # noqa: BLE001 — 任何失败都走退避，错误信息只记类型
            status, run_after = after_failure(job.attempts, job.max_attempts, self._clock())
            await self._store.fail(job_id=job.id, owner=self._owner, status=status, run_after=run_after,
                                   error=type(exc).__name__)
            log.warning("job failed", extra={"kind": job.kind, "attempts": job.attempts, "status": status})
        else:
            await self._store.complete(job_id=job.id, owner=self._owner)
        finally:
            renewer.cancel()
            await asyncio.gather(renewer, return_exceptions=True)

    async def _renew(self, job: JobRecord) -> None:
        while True:
            await asyncio.sleep(self._renew_every)
            if not await self._store.renew(job_id=job.id, owner=self._owner, lease_until=self._clock() + LEASE):
                log.error("job lease lost", extra={"kind": job.kind})
                return
