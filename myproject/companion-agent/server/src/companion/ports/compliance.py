"""合规底座要持久化的两样东西：用户同意、连续使用计时（docs/her-companion-research.md 第 7 节）。

- 训练用途同意默认关闭，必须用户明确打开；proactive_enabled 是用户对「主动联系」的总开关。
- 连续使用：超过 30 分钟没有活跃算新的一段；一段内到 2 小时提醒一次（取各地区最严：纽约 3 小时、国内 2 小时）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

SPAN_GAP_MINUTES = 30
REMIND_AFTER_MINUTES = 120


@dataclass(frozen=True)
class Consent:
    training_consent: bool = False
    proactive_enabled: bool = True
    age_verified_adult: bool = False
    qa_retention: bool = False


@dataclass(frozen=True)
class UsageState:
    """一次「看到用户又用了」之后的结果：是否需要提醒、这一段已经用了多久。"""

    span_minutes: int
    should_remind: bool = False


class ComplianceStore(Protocol):
    async def consent(self, *, owner_id: int) -> Consent: ...

    async def update_consent(self, *, owner_id: int, training_consent: bool | None = None,
                             proactive_enabled: bool | None = None,
                             age_verified_adult: bool | None = None,
                             qa_retention: bool | None = None) -> Consent: ...

    async def touch_usage(self, *, owner_id: int, now: datetime) -> UsageState:
        """记一次活跃；同一段里到 2 小时且还没提醒过 → should_remind=True（只提醒一次）。"""
        ...

    async def delete_user(self, *, owner_id: int) -> int: ...
