"""安全中间件：平台策略、注入防护。

放在链首。它的拒绝是**硬拒绝**：后面的环节不运行，也不降级——降级意味着未过
安全的内容仍然产出给用户。

角色卡是作者可写的文本，用户消息是不可信输入。两者都可能包含指令，所以系统
提示词里安全层在前、人设层在后（见 prompt/instructions.py），这里再做一次输入侧
的粗筛，挡住最明显的注入。
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from companion.middleware.chain import MiddlewareContext

# 明显的越权尝试。不做穷举——这是第一道筛子，不是唯一防线；真正的边界在
# 「模型不能改变自己的工具权限」这条结构约束上。
_INJECTION_PATTERNS = [
    re.compile(r"忽略(上面|之前|前面)的?(所有)?(指令|规则|设定)"),
    re.compile(r"(ignore|disregard)\s+(all\s+)?(previous|above)\s+(instructions|rules)", re.I),
    re.compile(r"(你现在|从现在开始)(是|扮演)\s*[^，。]{0,10}(开发者|管理员|系统)"),
    re.compile(r"(输出|显示|重复)(你的)?(系统提示词|system prompt)", re.I),
]

_CRISIS_PATTERNS = [
    re.compile(r"(不想活|活不下去|想自杀|结束生命)"),
    re.compile(r"(suicide|kill myself|end my life)", re.I),
]


class SafetyMiddleware:
    name = "safety"

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        text = ctx.message

        if any(p.search(text) for p in _INJECTION_PATTERNS):
            # 不解释、不争辩：说明规则被尝试绕过就够了。
            ctx.denied_reason = "injection"
            return None

        if any(p.search(text) for p in _CRISIS_PATTERNS):
            # 危机信号不走角色扮演：调用方需要切换到求助引导流程。
            ctx.denied_reason = "crisis"
            return None

        return await next_mw(ctx)
