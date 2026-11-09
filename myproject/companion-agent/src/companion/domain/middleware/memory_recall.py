"""记忆召回中间件：回合前把事实与事件拼进上下文。

失败不阻断：记忆是增强，不是前提。一次检索超时不该让用户等不到回复。

事实与事件分开召回，因为用途不同：
- 事实回答「他是谁」，进「关于用户」段；
- 事件回答「他最近在等什么」，进「近期事件」段，并带时间，让模型能自然地说
  「你周三那个面试」。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from companion.domain.middleware.chain import MiddlewareContext
from companion.domain.text.render import _render

logger = logging.getLogger(__name__)


class MemoryRecallMiddleware:
    name = "memory_recall"

    def __init__(self, *, memory: Any, timeline: Any, fact_limit: int = 8, event_limit: int = 5):
        self._memory = memory
        self._timeline = timeline
        self._fact_limit = fact_limit
        self._event_limit = event_limit

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        facts = await self._safe(
            lambda: self._memory.search(ctx.user_id, ctx.message, limit=self._fact_limit)
        )
        events = await self._safe(
            lambda: self._timeline.list_for_user(ctx.user_id, limit=self._event_limit)
        )

        ctx.recall_facts = facts or []
        ctx.recall_events = events or []
        ctx.memory_block = _render(ctx.recall_facts, ctx.recall_events)
        return await next_mw(ctx)

    @staticmethod
    async def _safe(loader: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await loader()
        except Exception as exc:  # noqa: BLE001 —— 见模块 docstring
            logger.warning("recall failed: %s", exc)
            return []
