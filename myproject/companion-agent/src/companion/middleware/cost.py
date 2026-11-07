"""成本与预算中间件。

放在链尾，因为它要看到前面所有环节产生的用量。

主动回合也要计入同一份预算：频繁推送同时烧钱的组合最难被发现，因为两个系统
各自看都正常。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from companion.middleware.chain import MiddlewareContext

logger = logging.getLogger(__name__)


class CostMiddleware:
    name = "cost"

    def __init__(self, *, budget_tokens: int = 32_000, usage_sink: Any = None):
        self._budget = budget_tokens
        self._usage_sink = usage_sink

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        result = await next_mw(ctx)
        spent = ctx.usage.get("total_tokens", 0)
        if spent > self._budget:
            # 不在这里截断输出——截断已经流出去的内容会让语音断在半句上。
            # 记录并在下一回合收紧，是更安全的做法。
            logger.warning(
                "turn over budget: user=%s spent=%s budget=%s",
                ctx.user_id,
                spent,
                self._budget,
            )
        if self._usage_sink is not None:
            try:
                self._usage_sink(ctx.user_id, ctx.usage)
            except Exception as exc:  # noqa: BLE001
                logger.debug("usage sink failed: %s", exc)
        return result
