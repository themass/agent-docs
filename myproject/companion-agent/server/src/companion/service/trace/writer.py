"""旁路写入器：把“质检记录”从回复路径上拿开。

为什么需要：回合的追踪写入原来在模型调用的 ``finally`` 里同步执行，``TurnRunner`` 要等它写完才保存助手消息、
发 ``message.done``、释放会话锁。远程库往返几百毫秒很常见，一个回合要几次往返，用户就多等几秒，
会话锁也多占几秒。记录是旁路，不该有这个代价。

做法：任务放进**有界**内存队列，由后台任务写库。
- **满了就丢**并计数，不阻塞回复：质检数据丢一点没关系，回答变慢有关系。队列大小决定最多积压多少。
- **进程崩溃会丢队列里的记录**。这是明确接受的取舍：这些是质检数据，不是业务数据；业务数据
  （消息、回合状态以外的一切）仍在回复路径上同步写。
- 退出时在期限内排空（``close``），超时就放弃剩下的并记日志，不拖住关停。
- 单个任务失败只记日志，不影响其他任务。

本模块只依赖 asyncio，不认识数据库。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

log = logging.getLogger("companion.trace")

Job = Callable[[], Awaitable[None]]
DEFAULT_QUEUE = 1000
DEFAULT_WORKERS = 2
LOG_EVERY = 100          # 连续丢弃时每 N 次记一条，免得队列堵住时刷屏


@dataclass
class WriterStats:
    queued: int = 0
    written: int = 0
    failed: int = 0
    dropped: int = 0

    @property
    def pending(self) -> int:
        return self.queued - self.written - self.failed


class BackgroundWriter:
    def __init__(self, *, max_queue: int = DEFAULT_QUEUE, workers: int = DEFAULT_WORKERS) -> None:
        self._max_queue = max_queue
        self._workers_n = max(1, workers)
        self._queue: asyncio.Queue[Job] | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self.stats = WriterStats()

    def submit(self, job: Job) -> bool:
        """放进队列。队列满、或已关闭返回 False（并计入 dropped）。**从不阻塞、从不抛错。**"""
        try:
            queue = self._ensure_started()
        except RuntimeError:
            return self._drop("no running loop")
        try:
            queue.put_nowait(job)
        except asyncio.QueueFull:
            return self._drop("queue full")
        self.stats.queued += 1
        return True

    def _drop(self, why: str) -> bool:
        self.stats.dropped += 1
        if self.stats.dropped == 1 or self.stats.dropped % LOG_EVERY == 0:
            log.warning("trace write dropped (%s); total dropped=%d", why, self.stats.dropped)
        return False

    def _ensure_started(self) -> asyncio.Queue[Job]:
        # 懒启动：第一次提交时才建队列和 worker，所以不依赖构造时有没有运行中的事件循环
        loop = asyncio.get_running_loop()
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_queue)
            self._tasks = [loop.create_task(self._run()) for _ in range(self._workers_n)]
        return self._queue

    async def _run(self) -> None:
        assert self._queue is not None
        while True:
            job = await self._queue.get()
            try:
                await job()
                self.stats.written += 1
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 —— 一个任务失败不能让 worker 退出
                self.stats.failed += 1
                log.warning("trace write failed", exc_info=True)
            finally:
                self._queue.task_done()

    async def flush(self, timeout: float = 10.0) -> bool:
        """等队列里已有的任务写完。返回是否在期限内全部完成。"""
        if self._queue is None:
            return True
        try:
            await asyncio.wait_for(self._queue.join(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def close(self, timeout: float = 10.0) -> None:
        """排空并停止。必须在关闭数据库连接之前调用：worker 写库用的就是那些连接。"""
        drained = await self.flush(timeout)
        if not drained:
            log.warning("trace writer closed with %d unwritten jobs", self.stats.pending)
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks, self._queue = [], None
