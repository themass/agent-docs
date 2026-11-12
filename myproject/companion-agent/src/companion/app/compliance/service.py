"""合规底座：同意、连续使用提醒、数据导出、主动消息总开关（调研报告 P0-a）。

只做「每一条都必须在服务端成立」的部分：

- **同意**：训练用途默认关闭，用户自己打开；主动联系有总开关。
- **连续使用提醒**：每次用户发消息记一次活跃；一段内到 2 小时，在该回合的 SSE 里带一条提醒
  （客户端展示），同一段只提醒一次。跨地区取最严：国内 2 小时、纽约 3 小时、加州只看已知未成年人。
- **数据导出**：用户能拿到自己的全部数据（记忆、画像、事件、消息、提醒）。办法要求可复制。
- **主动消息总开关**：关掉后调度器不再发起主动回合；用户明确要求的提醒仍会到期执行（那是兑现请求）。

不做的（需要客户端或别的系统）：显式 AI 标识的展示、未成年人年龄识别、紧急联系人流程。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from companion.ports.compliance import Consent

log = logging.getLogger("companion.compliance")

USAGE_REMINDER_TEXT = "我们已经连续聊了很久了。要不要先歇一会儿，或者去见见身边的人？我一直在。"


class ComplianceService:
    def __init__(self, *, store: Any) -> None:
        self._store = store     # ComplianceStore

    async def consent(self, *, owner_id: int) -> Consent:
        return await self._store.consent(owner_id=owner_id)

    async def update(self, *, owner_id: int, training_consent: bool | None = None,
                     proactive_enabled: bool | None = None, age_verified_adult: bool | None = None) -> Consent:
        return await self._store.update_consent(
            owner_id=owner_id, training_consent=training_consent,
            proactive_enabled=proactive_enabled, age_verified_adult=age_verified_adult)

    async def proactive_allowed(self, *, owner_id: int) -> bool:
        """主动联系是否允许。查询失败时按不允许处理（fail-closed）。"""
        try:
            return (await self._store.consent(owner_id=owner_id)).proactive_enabled
        except Exception:  # noqa: BLE001
            log.warning("consent read failed, treating proactive as disabled", extra={"owner_id": owner_id})
            return False

    async def note_activity(self, *, owner_id: int) -> str | None:
        """记一次活跃；该提醒时返回提醒文案，否则 None。计时失败不影响回合。"""
        try:
            state = await self._store.touch_usage(owner_id=owner_id, now=datetime.now(UTC))
        except Exception:  # noqa: BLE001
            log.warning("usage tracking failed", extra={"owner_id": owner_id})
            return None
        return USAGE_REMINDER_TEXT if state.should_remind else None


async def export_user_data(*, owner_id: int, sessions: Any, messages: Any, persona: Any,
                           timeline: Any, reminders: Any, consent: Any) -> dict[str, Any]:
    """导出该用户的全部数据。任何一块读不到就如实标注，不假装完整。"""
    out: dict[str, Any] = {"exported_at": datetime.now(UTC).isoformat(), "owner_id": owner_id}
    errors: list[str] = []

    async def guard(name: str, fn):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 —— 一块失败不该让整份导出失败
            errors.append(f"{name}: {type(exc).__name__}")
            return None

    out["consent"] = await guard("consent", lambda: consent.consent(owner_id=owner_id))
    out["sessions"] = await guard("sessions", lambda: sessions.list_for_owner(owner_id=owner_id, limit=500, offset=0))
    conversations = []
    for record in out["sessions"] or []:
        page = await guard(f"messages:{record.id}",
                           lambda sid=record.id: messages.list_before(owner_id=owner_id, session_id=sid,
                                                                     before_id=None, limit=500))
        conversations.append({"session_id": record.id, "messages": page or []})
    out["conversations"] = conversations
    out["profile"] = (await guard("profile", lambda: persona.list_entries(
        owner_id=owner_id, role_id="", include_history=True))) if persona is not None else []
    out["timeline"] = await guard("timeline", lambda: timeline.list_for_owner(
        owner_id=str(owner_id), include_past=True, limit=500))
    out["reminders"] = await guard("reminders", lambda: reminders.list(owner_id=owner_id, include_done=True))
    if errors:
        out["partial_errors"] = errors
    return out
