"""观测中间件：耗时、用量、链路标记。

不阻断主流程：观测本身失败不该让用户看不到回复。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from companion.middleware.chain import MiddlewareContext

logger = logging.getLogger("companion.turn")


class ObservabilityMiddleware:
    name = "observability"

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        started = time.perf_counter()
        try:
            return await next_mw(ctx)
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            # 主动回合单独标记：排查「她为什么突然找我」时这是第一现场。
            logger.info(
                "turn user=%s character=%s mode=%s proactive=%s elapsed_ms=%s denied=%s",
                ctx.user_id,
                ctx.character_id,
                ctx.mode,
                ctx.proactive,
                elapsed_ms,
                ctx.denied_reason,
            )
