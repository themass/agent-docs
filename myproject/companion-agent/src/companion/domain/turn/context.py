"""回合运行时上下文。

必须是 TypedDict（即 Mapping）：DeerFlow 的交互策略只读取 Mapping 形式的 context（P §2.2）。
图内中间件通过它拿到本回合的身份、提示词、允许的工具与 steer 收件箱，不走全局变量。
"""

from __future__ import annotations

from typing import Any, TypedDict


class TurnRuntimeContext(TypedDict, total=False):
    user_id: str
    role_id: str
    locale: str
    turn_id: str
    system_prompt: str
    allowed_tools: frozenset[str]
    steer_inbox: Any          # domain.turn.steer.SteerInbox
    events: Any               # 发事件的回调，由适配器注入
    interaction_mode: str     # 固定为 "autonomous"，兜底抑制 ask_clarification（P §2.2）
