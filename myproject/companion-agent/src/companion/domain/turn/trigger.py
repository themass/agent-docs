"""触发器：一次交互的起点。

用户发消息只是其中一种；定时器、事件到期、外部 webhook 都会让 agent 开口。
归一成 [Trigger] 之后，下半条管线只有一份实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TriggerKind(str, Enum):
    USER_MESSAGE = "user_message"
    SCHEDULE = "schedule"
    EVENT_DUE = "event_due"
    WEBHOOK = "webhook"
    SYSTEM = "system"

    @property
    def is_proactive(self) -> bool:
        """主动：不由用户当前这轮输入发起。

        主动性影响的只是输出通道（推送、电话）与频率控制，不影响 agent 本身：
        它拿到的仍是同一套提示词、记忆与工具。
        """
        return self in {
            TriggerKind.SCHEDULE,
            TriggerKind.EVENT_DUE,
            TriggerKind.WEBHOOK,
        }


@dataclass(frozen=True)
class Trigger:
    kind: TriggerKind
    user_id: str
    character_id: str
    payload: dict = field(default_factory=dict)
    # 谁触发的：user / scheduler / event:<id> / webhook:<name>。审计与排障用。
    origin: str = "user"
    at: datetime | None = None

    def message(self) -> str:
        """给主脑的用户消息。

        主动触发时没有真正的用户输入，用一段系统描述代替。它必须读起来像事实，
        不像指令，否则模型会把它当成人说的话去回应。
        """
        if self.kind == TriggerKind.USER_MESSAGE:
            return str(self.payload.get("text", "")).strip()
        return str(self.payload.get("prompt", "")).strip() or self._default_prompt()

    def _default_prompt(self) -> str:
        if self.kind == TriggerKind.EVENT_DUE:
            title = self.payload.get("title", "用户之前提到的一件事")
            return f"（系统提示：{title} 的时间快到了。据此主动开口。）"
        if self.kind == TriggerKind.SCHEDULE:
            return "（系统提示：到了约定的问候时间。据此主动开口。）"
        return "（系统提示：触发了一次主动回合。）"


__all__ = ["Trigger", "TriggerKind"]
