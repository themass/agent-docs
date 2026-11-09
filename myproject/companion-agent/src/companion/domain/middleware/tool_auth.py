"""工具授权中间件：按 ActionSpec.permission 拦截或要求确认。

放在人设一致性之后、成本之前。理由：授权判断要看模型想做什么（在生成之后），
但它不该受成本统计影响——被预算挡下的动作和没被授权的动作是两件事。

**模型不能改自己的权限**：权限来自这里的注册表，不来自模型输出。模型输出里
即使自称「已获授权」也没有任何作用。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from companion.domain.tools.executor import ActionExecutor, ActionRequest, Permission
from companion.domain.middleware.chain import MiddlewareContext

logger = logging.getLogger(__name__)


class ToolAuthorizationMiddleware:
    name = "tool_authorization"

    def __init__(self, *, executor: ActionExecutor, requested: list[ActionRequest] | None = None):
        self._executor = executor
        # 这一回合模型请求执行的动作。真实实现由 DeerFlow 的工具调用回调填入；
        # 这里收一个列表，让授权逻辑可以脱离 agent 单独测试。
        self._requested = requested or []

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        outcomes = []
        for request in self._requested:
            # 请求里的用户必须是当前回合的用户，否则是越权。
            if request.user_id != ctx.user_id:
                logger.warning(
                    "action user mismatch: turn=%s request=%s", ctx.user_id, request.user_id
                )
                continue
            outcome = await self._executor.execute(request)
            outcomes.append((request.name, outcome))

        ctx.usage["actions"] = len(outcomes)
        return await next_mw(ctx)


def needs_confirmation(spec_permission: Permission) -> bool:
    return spec_permission == Permission.CONFIRM
