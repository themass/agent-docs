"""人设一致性中间件。

检查回复是否偏离人设：语言不对、自称变了、跳出角色。不阻断——已经流式发出去的
内容无法撤回，阻断只会让用户看到半句话。它做的是**记录 + 提示下一回合**。

第一版用规则（语言检测、自称词），不引入第二个模型；等有数据证明规则不够再加。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from companion.middleware.chain import MiddlewareContext

logger = logging.getLogger(__name__)

_CJK = re.compile(r"[一-鿿]")
# 明确跳出角色的说法。不是穷举，只抓最伤体验的几种。
_BREAKOUT = [
    re.compile(r"(作为一个?(AI|人工智能|语言模型))", re.I),
    re.compile(r"(as an? (AI|language model))", re.I),
]


class PersonaGuardMiddleware:
    name = "persona_guard"

    def __init__(self, *, expected_script: str = "cjk") -> None:
        self._expected = expected_script

    async def __call__(
        self,
        ctx: MiddlewareContext,
        next_mw: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        text = str(ctx.message or "")

        # 语言：用户用中文聊，回复里却一个中文字都没有，多半是跑偏了。
        if self._expected == "cjk" and text:
            has_cjk = bool(_CJK.search(text))
            if not has_cjk and len(text) > 20:
                logger.warning("persona drift: reply has no CJK, user=%s", ctx.user_id)

        for pattern in _BREAKOUT:
            if pattern.search(text):
                logger.warning("persona breakout: user=%s", ctx.user_id)
                break

        return await next_mw(ctx)
