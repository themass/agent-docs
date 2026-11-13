"""主动性策略。

这是整个系统里最该保守的地方：一次不合时宜的打扰，代价远大于少说一次话。
所以测试的重点都是「不该发的时候确实不发」。
"""

from datetime import UTC, datetime, time, timedelta

import pytest

from companion.service.proactive.policy import InitiativePolicy
from companion.service.proactive.models import InitiativePreferences, InitiativeState, SendRecord, Channel
from companion.service.turn.trigger import TriggerKind


def at(year=2026, month=11, day=7, hour=10, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def decide(policy, *, kind, payload=None, prefs=None, state=None, now=None):
    return policy.decide(
        kind=kind,
        payload=payload or {},
        preferences=prefs or InitiativePreferences(),
        state=state or InitiativeState(),
        now=now or at(),
    )


def test_interview_event_is_allowed():
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
    )
    assert decision.should_speak is True
    assert decision.channel == Channel.IN_APP


def test_low_confidence_event_does_not_disturb():
    """误报一次「你明天有面试」会让人怀疑整个功能。"""
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.3},
    )
    assert decision.should_speak is False
    assert decision.reason == "low_confidence"


def test_low_priority_event_does_not_disturb():
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "other", "confidence": 1.0},
    )
    assert decision.should_speak is False
    assert decision.reason == "low_priority"


def test_greetings_off_by_default():
    """默认只开重要事件，日常问候要用户主动打开。"""
    decision = decide(InitiativePolicy(), kind=TriggerKind.SCHEDULE)
    assert decision.should_speak is False
    assert decision.reason == "greetings_off"


def test_greetings_allowed_when_enabled():
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.SCHEDULE,
        prefs=InitiativePreferences(greetings_enabled=True),
    )
    assert decision.should_speak is True


def test_events_can_be_turned_off():
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
        prefs=InitiativePreferences(events_enabled=False),
    )
    assert decision.reason == "events_off"


@pytest.mark.parametrize("hour", [23, 0, 3, 7])
def test_quiet_hours_block(hour):
    """23:00–08:00 不发。这条错了会让用户在半夜收到推送。"""
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
        now=at(hour=hour),
    )
    assert decision.should_speak is False
    assert decision.reason == "quiet_hours"


@pytest.mark.parametrize("hour", [8, 12, 22])
def test_outside_quiet_hours_allow(hour):
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
        now=at(hour=hour),
    )
    assert decision.should_speak is True


def test_daily_cap_blocks_third_message():
    now = at()
    state = InitiativeState(
        sent=[SendRecord(at=now - timedelta(hours=1), channel=Channel.IN_APP, trigger="x")] * 2
    )
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
        state=state,
        now=now,
    )
    assert decision.reason == "daily_cap"


def test_weekly_cap_blocks():
    now = at()
    # 每天 1 条、连续 6 天：日上限没到，周上限到了。
    sent = [
        SendRecord(at=now - timedelta(days=d), channel=Channel.IN_APP, trigger="x")
        for d in range(1, 7)
    ]
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
        state=InitiativeState(sent=sent),
        now=now,
    )
    assert decision.reason == "weekly_cap"


def test_paused_blocks_everything():
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 1.0},
        prefs=InitiativePreferences(paused_until=at(hour=23)),
    )
    assert decision.reason == "paused"


def test_call_channel_only_when_explicitly_enabled():
    payload = {"event_kind": "interview", "confidence": 0.9}
    assert decide(InitiativePolicy(), kind=TriggerKind.EVENT_DUE, payload=payload).channel == (
        Channel.IN_APP
    )
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload=payload,
        prefs=InitiativePreferences(call_enabled=True),
    )
    assert decision.channel == Channel.CALL


def test_priority_is_exposed_for_explaining_why():
    """用户问「为什么给我发这条」时，系统要能答上来。"""
    decision = decide(
        InitiativePolicy(),
        kind=TriggerKind.EVENT_DUE,
        payload={"event_kind": "interview", "confidence": 0.9},
    )
    assert decision.priority > 0.5
