"""调度：定时扫描到期事件与沉默用户，产出主动触发。

它只负责「什么时候该判断」，判断本身在 [InitiativePolicy] 里，执行在调用方。
三件事分开，是因为它们的测试方式完全不同：调度靠时间，判断靠规则，执行靠通道。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from companion.service.proactive.models import InitiativeDecision, InitiativePreferences, InitiativeState
from companion.service.proactive.policy import InitiativePolicy
from companion.service.turn.trigger import Trigger, TriggerKind

logger = logging.getLogger(__name__)


@dataclass
class SchedulerResult:
    triggers: list[Trigger] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (user_id, reason)


class InitiativeScheduler:
    """扫描并产出主动触发。不发送——发送由调用方按通道决定。"""

    def __init__(
        self,
        *,
        timeline: Any,
        policy: InitiativePolicy | None = None,
        preferences_loader: Callable[[str], Awaitable[InitiativePreferences]] | None = None,
        state_loader: Callable[[str], Awaitable[InitiativeState]] | None = None,
        relationship_loader: Callable[[str, str], Awaitable[float | None]] | None = None,
        lookahead: timedelta = timedelta(minutes=5),
    ) -> None:
        self._timeline = timeline
        self._policy = policy or InitiativePolicy()
        self._preferences_loader = preferences_loader or _default_preferences
        self._state_loader = state_loader or _default_state
        self._relationship_loader = relationship_loader or _default_relationship
        self._lookahead = lookahead

    async def scan(self, *, now: datetime) -> SchedulerResult:
        window_end = now + self._lookahead
        due = await self._timeline.due_between(start=now, end=window_end)
        result = SchedulerResult()

        for event in due:
            preferences = await self._preferences_loader(event.user_id)
            state = await self._state_loader(event.user_id)
            role_id = event.source_character_id or DEFAULT_CHARACTER
            # 关系闸门：None = 还没聊过（不抬门槛）；数字 = 衰减后的有效温度。
            # 读失败按 None 而不是 0：闸门宁松勿严，真正的保守在「没把握就不发」的基线里
            try:
                warmth = await self._relationship_loader(event.user_id, role_id)
            except Exception:  # noqa: BLE001 —— 关系读不到不该让整个扫描轮失败
                warmth = None

            # 提醒时间可以早于事件发生时间（remind_before），这里按提醒点判断。
            remind_at = event.at - (event.remind_before or timedelta(0))
            if remind_at > window_end:
                continue

            payload = {
                "title": event.title,
                "event_id": event.id,
                "event_kind": getattr(event.kind, "value", "other"),
                "confidence": event.confidence,
                "at": event.at.isoformat(),
            }
            decision = self._policy.decide(
                kind=TriggerKind.EVENT_DUE,
                payload=payload,
                preferences=preferences,
                state=state,
                now=now,
                relationship_warmth=warmth,
            )
            if not decision.should_speak:
                result.skipped.append((event.user_id, decision.reason))
                continue

            result.triggers.append(
                Trigger(
                    kind=TriggerKind.EVENT_DUE,
                    user_id=event.user_id,
                    character_id=role_id,
                    payload={**payload, "channel": decision.channel.value},
                    origin=f"event:{event.id}",
                    at=now,
                )
            )
        return result


async def _default_preferences(user_id: str) -> InitiativePreferences:
    return InitiativePreferences()


async def _default_state(user_id: str) -> InitiativeState:
    return InitiativeState()


async def _default_relationship(user_id: str, role_id: str) -> float | None:
    return None


DEFAULT_CHARACTER = "linche"
