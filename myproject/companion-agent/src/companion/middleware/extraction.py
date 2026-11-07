"""事件抽取中间件：回合结束后异步把事件写进时间线。

为什么放在中间件而不是交给 agent：抽取必须每回合都发生。靠模型「记得去做」
是不可靠的——它会在长对话、工具调用、上下文压缩之后忘掉。

抽取用便宜模型（场景 `memory_extract`），与对话模型分开。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from companion.middleware.chain import MiddlewareContext

logger = logging.getLogger(__name__)

# 低于这个置信度不驱动主动提醒：一次误报的打扰，比少一次提醒代价大得多。
PROACTIVE_CONFIDENCE_FLOOR = 0.6


class EventExtractionMiddleware:
    name = "event_extraction"

    def __init__(self, *, extractor: Callable[..., Awaitable[list[Any]]], timeline: Any):
        self._extractor = extractor
        self._timeline = timeline

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        result = await next_mw(ctx)
        try:
            events = await self._extractor(
                conversation=ctx.message,
                user_id=ctx.user_id,
                character_id=ctx.character_id,
                message_id=f"{ctx.user_id}-{ctx.character_id}-turn",
            )
        except Exception as exc:  # noqa: BLE001 —— 抽取失败不该让回合失败
            logger.warning("event extraction failed: %s", exc)
            return result

        for event in events or []:
            try:
                await self._timeline.add(event)
            except Exception as exc:  # noqa: BLE001
                logger.warning("timeline write failed: %s", exc)
        ctx.extracted_events = list(events or [])
        return result


def drives_proactive(event: Any) -> bool:
    """这条事件值不值得主动提醒。

    置信度太低的只存着供对话引用，不拿来打扰用户。
    """
    return getattr(event, "confidence", 0.0) >= PROACTIVE_CONFIDENCE_FLOOR
