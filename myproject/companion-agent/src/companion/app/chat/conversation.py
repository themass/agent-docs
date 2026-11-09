"""会话编排：把触发、中间件、主脑串成一个回合。

这一层不依赖 LiveKit，也不依赖 HTTP。上层有三种：LiveKit 的 agent（语音与文字
共用一个房间）、HTTP 的 SSE 回合接口、以及主动性的调度器。三者都只调这里，
不各自重复拼装逻辑——否则「她」在三个入口里会逐渐变成三个人。

一次回合的路径：

    Trigger → 会话层（线程、上下文）→ 中间件链 → 主脑 → 输出

中间件链是唯一允许横切关注点存在的地方。这里不做记忆召回，也不做安全过滤——
它们各有自己的中间件，顺序由链定义。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from companion.ports.brain import BrainPort, TurnRequest
from companion.domain.middleware.chain import MiddlewareChain, MiddlewareContext
from companion.domain.turn.trigger import Trigger


@dataclass
class TurnContext:
    """一次回合的外部输入。

    ``proactive`` 来自触发类型，影响输出通道与频控，不影响 agent 本身。
    """

    user_id: str
    character_id: str
    message: str
    thread_id: str | None = None
    mode: str = "text"
    proactive: bool = False
    trigger_kind: str = "user_message"

    @classmethod
    def from_trigger(cls, trigger: Trigger, *, mode: str = "text") -> "TurnContext":
        return cls(
            user_id=trigger.user_id,
            character_id=trigger.character_id,
            message=trigger.message(),
            mode=mode,
            proactive=trigger.kind.is_proactive,
            trigger_kind=trigger.kind.value,
        )


@dataclass
class TurnResult:
    turn_id: str
    chunks: AsyncIterator[str]
    cancel: Any = field(default=None)
    # 中间件填进去的东西：调用方可能要看（如抽取到的事件、是否被安全拒绝）。
    context: MiddlewareContext | None = None

    async def cancel_turn(self) -> None:
        if self.cancel is not None:
            await self.cancel()

    @property
    def denied_reason(self) -> str | None:
        return self.context.denied_reason if self.context is not None else None


class ConversationService:
    """回合编排。

    ``chain`` 是中间件链，``prompt_builder`` 按层组装系统提示词，``brain`` 生成。
    三者都可替换，所以这一层能在没有 DeerFlow、没有 mem0 的情况下用 fake 完整跑通。
    """

    def __init__(
        self,
        *,
        brain: BrainPort,
        prompt_builder: Any,
        chain: MiddlewareChain,
    ) -> None:
        self._brain = brain
        self._prompt = prompt_builder
        self._chain = chain
        # 当前回合的取消入口。一个会话同时只有一个回合在跑：语音场景下新开口
        # 就是打断上一句，没有并行的意义。
        self._active_cancel: Any = None

    async def prepare(self, ctx: TurnContext) -> tuple[TurnRequest | None, MiddlewareContext]:
        """跑中间件链，产出主脑请求。

        被安全中间件拒绝时返回 ``(None, ctx)``：调用方据此换一条路径（危机引导、
        或直接忽略），而不是让模型在未过安全的前提下生成内容。
        """
        mw_ctx = MiddlewareContext(
            user_id=ctx.user_id,
            character_id=ctx.character_id,
            message=ctx.message,
            mode=ctx.mode,
            proactive=ctx.proactive,
        )

        async def terminal(current: MiddlewareContext) -> TurnRequest:
            system_prompt = self._prompt(
                ctx, current.memory_block
            )
            return TurnRequest(
                user_id=ctx.user_id,
                character_id=ctx.character_id,
                message=ctx.message,
                thread_id=ctx.thread_id,
                system_prompt=system_prompt,
                metadata={
                    "mode": ctx.mode,
                    "proactive": ctx.proactive,
                    "trigger": ctx.trigger_kind,
                },
            )

        request = await self._chain.run(mw_ctx, terminal)
        return request, mw_ctx

    async def start_turn(self, ctx: TurnContext) -> TurnResult:
        request, mw_ctx = await self.prepare(ctx)
        if request is None:
            # 被拒绝：给一个空流而不是抛错，上层的处理与正常回合一致。
            return TurnResult(
                turn_id="",
                chunks=_empty_stream(),
                cancel=None,
                context=mw_ctx,
            )

        turn = await self._brain.start_turn(request)
        self._active_cancel = turn.cancel_turn
        return TurnResult(
            turn_id=turn.turn_id,
            chunks=turn.tokens,
            cancel=turn.cancel_turn,
            context=mw_ctx,
        )

    async def cancel_current(self) -> None:
        """打断当前回合。没有正在跑的回合时是空操作。"""
        cancel, self._active_cancel = self._active_cancel, None
        if cancel is not None:
            await cancel()

    async def aclose(self) -> None:
        await self._brain.aclose()


async def _empty_stream() -> AsyncIterator[str]:
    return
    yield  # pragma: no cover —— 让函数成为异步生成器
