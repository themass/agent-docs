"""停机状态（P §3.5）。进程收到退出信号后：置 draining → 新发送返回 503 → 等回合收尾。"""

from __future__ import annotations

import asyncio


class DrainState:
    def __init__(self) -> None:
        self._draining = False
        self._active = 0
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def draining(self) -> bool:
        return self._draining

    @property
    def active_turns(self) -> int:
        return self._active

    def begin(self) -> None:
        self._draining = True

    def turn_started(self) -> None:
        self._active += 1
        self._idle.clear()

    def turn_finished(self) -> None:
        self._active = max(0, self._active - 1)
        if self._active == 0:
            self._idle.set()

    async def wait_idle(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self._idle.wait(), timeout)
            return True
        except TimeoutError:
            return False
