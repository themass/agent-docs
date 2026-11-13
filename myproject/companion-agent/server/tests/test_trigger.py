"""触发层的归一化。

重点是：主动触发必须能把「系统提示」变成一条可用的用户消息，且读起来不像指令。
"""

import pytest

from companion.turn.trigger import Trigger, TriggerKind


def test_user_message_trigger_uses_payload_text():
    trigger = Trigger(
        kind=TriggerKind.USER_MESSAGE,
        user_id="u1",
        character_id="linche",
        payload={"text": "  我最近有点累  "},
    )
    assert trigger.message() == "我最近有点累"
    assert trigger.kind.is_proactive is False


def test_event_trigger_mentions_the_event_title():
    trigger = Trigger(
        kind=TriggerKind.EVENT_DUE,
        user_id="u1",
        character_id="linche",
        payload={"title": "面试"},
    )
    message = trigger.message()
    assert "面试" in message
    assert trigger.kind.is_proactive is True


def test_proactive_message_is_marked_as_system_note():
    """主动消息若读起来像用户说的话，模型会当作用户真在说这句。"""
    for kind in (TriggerKind.EVENT_DUE, TriggerKind.SCHEDULE, TriggerKind.SYSTEM):
        trigger = Trigger(kind=kind, user_id="u1", character_id="linche")
        assert "系统提示" in trigger.message()


def test_explicit_prompt_overrides_default():
    trigger = Trigger(
        kind=TriggerKind.SCHEDULE,
        user_id="u1",
        character_id="linche",
        payload={"prompt": "早安"},
    )
    assert trigger.message() == "早安"


@pytest.mark.parametrize(
    "kind, expected",
    [
        (TriggerKind.USER_MESSAGE, False),
        (TriggerKind.SYSTEM, False),
        (TriggerKind.SCHEDULE, True),
        (TriggerKind.EVENT_DUE, True),
        (TriggerKind.WEBHOOK, True),
    ],
)
def test_is_proactive(kind, expected):
    assert kind.is_proactive is expected
