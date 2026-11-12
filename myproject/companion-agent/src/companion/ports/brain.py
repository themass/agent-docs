"""主脑接口。

一次回合 = 一个 [`BrainTurn`]：先拿到文本片段流，必要时可以取消。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from companion.domain.prompt.plan import PromptPlan


@dataclass
class BrainTurn:
    """一个回合的文本片段流，加上取消入口。

    ``tokens`` 只产出文本；工具调用、思考、用量等事件由实现自行消费，不下传。
    """

    tokens: AsyncIterator[str]
    cancel: "CancelFn"
    turn_id: str = ""
    # 这个回合对应的用户消息（落库后的主键）。语音质检记录用它把识别文本和消息表对上；没有时为 None。
    user_message_id: int | None = None

    async def cancel_turn(self) -> None:
        await self.cancel()


CancelFn = "Callable[[], Awaitable[None]]"


@dataclass(frozen=True)
class TurnInputMessage:
    """本回合的一条用户输入。``message_id`` 是消息表主键，大脑用它生成稳定的消息 id，
    这样合并重跑、插话、删除、重新生成都能按 id 精确操作（chat-agent-next-plan.md §2.2）。"""

    message_id: int
    text: str


@dataclass
class TurnRequest:
    """一次回合的输入。

    ``session_id`` 决定大脑的对话线程（历史由大脑的 checkpoint 按会话保存）。
    ``inputs`` 是本回合覆盖的用户消息；为空时退回 ``message``（语音等旧链路）。
    ``prompt`` 是本轮的提示词计划（系统提示词 + 按深度注入）；为空时用 ``system_prompt``。
    """

    user_id: str
    character_id: str
    message: str
    thread_id: str | None = None
    system_prompt: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    session_id: int | None = None
    inputs: tuple[TurnInputMessage, ...] = ()
    prompt: PromptPlan | None = None


class TurnRefused(Exception):
    """输入被拒绝（内容安全等）。调用方应该让用户听到/看到一句回应，而不是沉默。"""

    def __init__(self, reason: str | None) -> None:
        super().__init__(reason or "refused")
        self.reason = reason or ""


class BrainPort(Protocol):
    async def start_turn(self, request: TurnRequest) -> BrainTurn: ...

    async def aclose(self) -> None: ...


# ---- 图事件（T4）：适配器把 DeerFlow 的流翻译成这些，回合层只认它们 ----

@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolStarted:
    call_id: str
    name: str


@dataclass(frozen=True)
class ToolFinished:
    call_id: str
    name: str
    content: str


@dataclass(frozen=True)
class GraphMessageIds:
    """本次尝试里大脑写进对话线程的消息 id（助手回复、工具调用与结果）。

    回合层把它们记到助手消息的 meta 里，之后删除或重新生成时按 id 从线程里移除。"""

    ids: tuple[str, ...]


BrainEvent = TextDelta | ToolStarted | ToolFinished | GraphMessageIds
