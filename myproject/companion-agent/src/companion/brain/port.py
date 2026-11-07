"""主脑接口。

一次回合 = 一个 [`BrainTurn`]：先拿到文本片段流，必要时可以取消。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class BrainTurn:
    """一个回合的文本片段流，加上取消入口。

    ``tokens`` 只产出文本；工具调用、思考、用量等事件由实现自行消费，不下传。
    """

    tokens: AsyncIterator[str]
    cancel: "CancelFn"
    turn_id: str = ""

    async def cancel_turn(self) -> None:
        await self.cancel()


CancelFn = "Callable[[], Awaitable[None]]"


@dataclass
class TurnRequest:
    """一次回合的输入。

    ``user_id`` 与 ``character_id`` 一起决定记忆与线程；``thread_id`` 为空时由
    实现方新建，用于把多轮对话串起来。
    """

    user_id: str
    character_id: str
    message: str
    thread_id: str | None = None
    system_prompt: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class BrainPort(Protocol):
    async def start_turn(self, request: TurnRequest) -> BrainTurn: ...

    async def aclose(self) -> None: ...
