"""确认闭环（T §2.4）：查看待确认、允许、拒绝。

允许：先认领（pending→processing，原子），再用快照参数执行，最后记录结果。
同一条确认只能被处理一次；两次点击只有第一次生效。
执行完写一条 kind='action' 的助手消息，不起新的模型回合。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from companion.app.tools.runtime import ToolRuntime
from companion.ports.store import ConfirmationRecord, ConfirmationStore, MessageStore


@dataclass(frozen=True)
class ConfirmResult:
    status: str                      # executed | declined | expired | failed
    message_id: int | None = None


class ConfirmationService:
    def __init__(self, *, store: ConfirmationStore, messages: MessageStore, runtime: ToolRuntime,
                 clock=lambda: datetime.now(UTC)) -> None:
        self._store = store
        self._messages = messages
        self._runtime = runtime
        self._clock = clock

    async def pending(self, *, owner_id: int) -> list[ConfirmationRecord]:
        return await self._store.list_pending(owner_id=owner_id)

    async def decide(self, *, owner_id: int, confirmation_id: str, accept: bool) -> ConfirmResult | None:
        """返回 None 表示不存在、不属于本人、或已处理（路由层统一 404，§5.3）。"""
        record = await self._store.get_pending(owner_id=owner_id, confirmation_id=confirmation_id)
        if record is None:
            return None
        if record.expires_at <= self._clock():
            await self._store.decide(owner_id=owner_id, confirmation_id=confirmation_id, status="expired")
            return ConfirmResult("expired")
        if not accept:
            if not await self._store.decide(owner_id=owner_id, confirmation_id=confirmation_id, status="declined"):
                return None
            message = await self._note(owner_id, record, f"已取消：{record.title}")
            return ConfirmResult("declined", message.id)

        # 认领：pending→processing。并发的第二次点击在这里失败。
        if not await self._store.decide(owner_id=owner_id, confirmation_id=confirmation_id, status="processing"):
            return None
        outcome = await self._runtime.run_confirmed(
            owner_id=owner_id, session_id=record.session_id, turn_id=record.turn_id or "",
            character_id="", locale="", name=record.tool, args=dict(record.args or {}),
            confirmation_id=confirmation_id)
        status = "executed" if outcome.status == "executed" else "failed"
        await self._store.finish(owner_id=owner_id, confirmation_id=confirmation_id, status=status)
        text = f"已完成：{record.title}" if status == "executed" else f"未能完成：{record.title}，请稍后重试"
        message = await self._note(owner_id, record, text)
        return ConfirmResult(status, message.id)

    async def _note(self, owner_id: int, record: ConfirmationRecord, text: str):
        return await self._messages.append(
            owner_id=owner_id, session_id=record.session_id, role="assistant", content=text,
            kind="action", client_message_id=None, turn_id=record.turn_id, meta={"confirmation_id": record.id})
