"""停机状态（P §3.5）。进程收到退出信号后：置 draining → 新发送返回 503 → 等回合收尾。

日志不是装饰：2026-11-28 线上有一次重启正好打断了一个刚起步的回合（session 39），
而 journal 里**没有任何一条**能证明 drain 跑过、当时有几个回合在飞。事后只能靠
时间戳相邻去猜。没有这两行日志，「优雅停机是否生效」在生产上不可判定。
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger("companion.drain")


class DrainState:
    def __init__(self) -> None:
        self._draining = False
        self._active = 0
        self._idle = asyncio.Event()
        self._idle.set()
        self._started: float | None = None

    @property
    def draining(self) -> bool:
        return self._draining

    @property
    def active_turns(self) -> int:
        return self._active

    def begin(self) -> None:
        if self._draining:
            return
        self._draining = True
        self._started = time.monotonic()
        # active=0 也要打：它是「停机时没有回合在飞」的正面证据，和「drain 没跑」在两处不同。
        log.info("drain begin active_turns=%d", self._active)

    def turn_started(self) -> None:
        self._active += 1
        self._idle.clear()

    def turn_finished(self) -> None:
        self._active = max(0, self._active - 1)
        if self._active == 0:
            self._idle.set()

    async def wait_idle(self, timeout: float) -> bool:
        ok = True
        try:
            await asyncio.wait_for(self._idle.wait(), timeout)
        except TimeoutError:
            ok = False
        # 等满超时还有回合在飞 = 它们会被后面的 SIGKILL 打断，用户那边就是「发了没反应」。
        # 这一行是把那件事从推测变成记录。
        if ok:
            waited = 0.0 if self._started is None else time.monotonic() - self._started
            log.info("drain idle after %.1fs", waited)
        else:
            log.warning("drain timed out after %.1fs with active_turns=%d — turns will be dropped",
                        timeout, self._active)
        return ok
