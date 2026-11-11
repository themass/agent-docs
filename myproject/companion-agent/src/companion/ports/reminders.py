"""定时提醒（主动消息）的持久化端口。

流程（chat-agent-next-plan.md 阶段 4）：模型调用 ``create_reminder`` 工具 → 用户确认 → 写一条 pending
→ 调度器到点认领（多副本互斥，租约过期可被他人接手）→ 发起一个主动回合 → 标记 sent。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

PENDING = "pending"
CLAIMED = "claimed"
SENT = "sent"
CANCELLED = "cancelled"
FAILED = "failed"


@dataclass(frozen=True)
class ReminderRecord:
    id: int
    owner_id: int
    session_id: int
    role_id: str
    due_at: datetime          # UTC，无时区信息
    timezone: str
    content: str
    status: str
    attempts: int
    created_at: datetime
    confirmation_id: str | None = None
    sent_turn_id: str | None = None


class ReminderStore(Protocol):
    async def create(self, *, owner_id: int, session_id: int, role_id: str, due_at: datetime, timezone: str,
                     content: str, confirmation_id: str | None) -> ReminderRecord:
        """同一 ``confirmation_id`` 重复创建时返回已有那条（幂等）。"""
        ...

    async def list_for_owner(self, *, owner_id: int, include_done: bool = False,
                             limit: int = 50) -> list[ReminderRecord]: ...

    async def cancel(self, *, owner_id: int, reminder_id: int) -> bool:
        """只有 pending 的可以取消。"""
        ...

    async def claim_due(self, *, owner: str, now: datetime, lease_until: datetime,
                        limit: int) -> list[ReminderRecord]:
        """认领到期的 pending，以及租约已过期的 claimed（视为上一个进程已崩溃）。"""
        ...

    async def mark_sent(self, *, reminder_id: int, owner: str, turn_id: str | None) -> bool: ...

    async def release(self, *, reminder_id: int, owner: str, error: str, retry_at: datetime | None,
                      max_attempts: int) -> bool:
        """发送失败：未超过次数则回到 pending（retry_at 之后再试），否则置 failed。"""
        ...
