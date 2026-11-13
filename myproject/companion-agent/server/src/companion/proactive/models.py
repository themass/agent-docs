"""主动性：her 与聊天机器人的分界线。

它是一个独立子系统，不是对话里的 if 分支。理由：

- 触发源不同（定时器、事件到期、沉默），与用户说话走的是完全不同的路径；
- 约束不同（频控、安静时段、退订），这些在对话路径里没有意义；
- 失败代价不同：对话里回错一句话是体验问题，半夜误发一条推送是信任问题。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum


class Channel(str, Enum):
    IN_APP = "in_app"
    PUSH = "push"
    CALL = "call"


@dataclass
class InitiativePreferences:
    """用户对「她主动找你」的偏好。全部可关。"""

    # 默认：重要事件提醒开，日常问候关。默认全开会被当成打扰。
    events_enabled: bool = True
    greetings_enabled: bool = False
    # 主动电话默认关闭：这是一件侵入性很强的事。
    call_enabled: bool = False
    quiet_start: time = time(23, 0)
    quiet_end: time = time(8, 0)
    max_per_day: int = 2
    max_per_week: int = 6
    paused_until: datetime | None = None


@dataclass
class InitiativeDecision:
    """一次判断的结果。带 reason，用户问「为什么给我发这个」时能答上来。"""

    should_speak: bool
    channel: Channel = Channel.IN_APP
    reason: str = ""
    priority: float = 0.0


@dataclass
class SendRecord:
    at: datetime
    channel: Channel
    trigger: str


@dataclass
class InitiativeState:
    """频控需要的记录。按用户聚合。"""

    sent: list[SendRecord] = field(default_factory=list)

    def count_within(self, *, now: datetime, days: int) -> int:
        from datetime import timedelta

        cutoff = now - timedelta(days=days)
        return sum(1 for record in self.sent if record.at >= cutoff)
