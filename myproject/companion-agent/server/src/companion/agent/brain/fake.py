"""测试用主脑：把预置文本按块吐出来，可断言取消。

它不是 mock 框架的替身，而是一个确定性的实现：同样的输入永远得到同样的片段，
这样上层（断句、事件映射、打断）的测试不依赖模型。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from companion.agent.brain.port import BrainTurn, TurnRequest


class FakeBrain:
    def __init__(self, script: Sequence[str] | None = None, *, delay: float = 0.0) -> None:
        self._script = list(script or ["你好呀。", "今天想聊点什么？"])
        self._delay = delay
        self.cancelled: list[str] = []
        self.requests: list[TurnRequest] = []

    async def start_turn(self, request: TurnRequest) -> BrainTurn:
        self.requests.append(request)
        turn_id = f"turn-{len(self.requests)}"
        cancelled = asyncio.Event()

        async def tokens():
            for chunk in self._script:
                if cancelled.is_set():
                    return
                if self._delay:
                    await asyncio.sleep(self._delay)
                yield chunk

        async def cancel() -> None:
            cancelled.set()
            self.cancelled.append(turn_id)

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id=turn_id)

    async def aclose(self) -> None:
        return None
