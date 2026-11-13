"""要不要开口的判断。

这个类是整个主动系统里最该保守的地方：一次不合时宜的打扰，代价远大于少说一次话。
所以所有判断都是「没把握就不发」。
"""

from __future__ import annotations

from datetime import datetime, time

from companion.proactive.models import Channel, InitiativeDecision, InitiativePreferences, InitiativeState
from companion.turn.trigger import TriggerKind

# 事件的重要度基线。面试和生日值得打扰，一个模糊的「旅行」不值得。
_PRIORITY_BY_KIND = {
    "interview": 0.9,
    "exam": 0.85,
    "appointment": 0.7,
    "birthday": 0.8,
    "anniversary": 0.75,
    "trip": 0.5,
    "other": 0.3,
}

# 低于这个分数不发。分数不够高时宁可安静。
_MIN_PRIORITY = 0.6
# 问候用另一条阈值：它本来就比事件轻，用事件的门槛会让「用户打开了问候」
# 这个设置变成一句空话。用户显式打开，就已经表达了「可以被打扰」。
_GREETING_MIN_PRIORITY = 0.4


class InitiativePolicy:
    def __init__(
        self,
        *,
        min_priority: float = _MIN_PRIORITY,
        proactive_confidence_floor: float = 0.6,
    ) -> None:
        self._min_priority = min_priority
        self._confidence_floor = proactive_confidence_floor

    def decide(
        self,
        *,
        kind: TriggerKind,
        payload: dict,
        preferences: InitiativePreferences,
        state: InitiativeState,
        now: datetime,
    ) -> InitiativeDecision:
        if preferences.paused_until is not None and now < preferences.paused_until:
            return InitiativeDecision(False, reason="paused")

        if kind == TriggerKind.SCHEDULE and not preferences.greetings_enabled:
            return InitiativeDecision(False, reason="greetings_off")

        if kind == TriggerKind.EVENT_DUE and not preferences.events_enabled:
            return InitiativeDecision(False, reason="events_off")

        if self._in_quiet_hours(now.time(), preferences):
            return InitiativeDecision(False, reason="quiet_hours")

        if state.count_within(now=now, days=1) >= preferences.max_per_day:
            return InitiativeDecision(False, reason="daily_cap")

        if state.count_within(now=now, days=7) >= preferences.max_per_week:
            return InitiativeDecision(False, reason="weekly_cap")

        priority = self._priority(kind, payload)
        threshold = (
            _GREETING_MIN_PRIORITY if kind == TriggerKind.SCHEDULE else self._min_priority
        )
        if priority < threshold:
            return InitiativeDecision(False, reason="low_priority", priority=priority)

        confidence = payload.get("confidence", 1.0)
        if kind == TriggerKind.EVENT_DUE and confidence < self._confidence_floor:
            # 抽取不确定的事件不打扰：误报一次「你明天有面试」会让人怀疑整件事。
            return InitiativeDecision(False, reason="low_confidence", priority=priority)

        channel = self._channel(kind, preferences)
        return InitiativeDecision(True, channel=channel, reason="ok", priority=priority)

    @staticmethod
    def _priority(kind: TriggerKind, payload: dict) -> float:
        if kind == TriggerKind.EVENT_DUE:
            return _PRIORITY_BY_KIND.get(str(payload.get("event_kind", "other")), 0.3)
        if kind == TriggerKind.SCHEDULE:
            # 日常问候永远低于事件：它是锦上添花，不是必须。
            return 0.55 if payload.get("important") else 0.45
        return 0.2

    @staticmethod
    def _channel(kind: TriggerKind, preferences: InitiativePreferences) -> Channel:
        # 电话只在用户显式开启、且是重要事件时才用；其余走应用内消息。
        if kind == TriggerKind.EVENT_DUE and preferences.call_enabled:
            return Channel.CALL
        return Channel.IN_APP

    @staticmethod
    def _in_quiet_hours(now: time, preferences: InitiativePreferences) -> bool:
        start, end = preferences.quiet_start, preferences.quiet_end
        if start <= end:
            return start <= now < end
        # 跨午夜，例如 23:00–08:00。
        return now >= start or now < end
