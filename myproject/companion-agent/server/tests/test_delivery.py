"""投递层：通道适配与记账。

这一层的测试重点不是「发出去了」，而是「发出去了有没有记账」与「没发出去会不会
被当成发出去了」。前者错了会连发，后者错了会让用户永远收不到。
"""

import pytest

from companion.domain.proactive.models import Channel, InitiativePreferences
from companion.app.proactive.router import ChannelRouter
from companion.ports.delivery import DeliveryError
from companion.adapters.delivery.memory import InAppDelivery, InMemorySendLedger, PushDelivery, RecordingDelivery


def at(hour=10):
    from datetime import UTC, datetime

    return datetime(2026, 11, 7, hour, 0, tzinfo=UTC)


async def send(router, *, channel=Channel.IN_APP, meta=None):
    return await router.send(
        user_id="u1",
        character_id="linche",
        text="面试准备得怎么样？",
        channel=channel,
        trigger="event:e1",
        at=at(),
        meta=meta,
    )


async def test_in_app_delivery_is_readable_by_the_client():
    """v1 的通道就是收件箱：客户端轮询拿到的就是发出去的那条。"""
    box = InAppDelivery()
    receipt = await send(ChannelRouter({Channel.IN_APP: box}))

    pending = await box.inbox("u1")
    assert [r.id for r in pending] == [receipt.id]
    assert pending[0].text == "面试准备得怎么样？"
    assert pending[0].character_id == "linche"


async def test_drain_removes_what_the_client_confirmed():
    box = InAppDelivery()
    router = ChannelRouter({Channel.IN_APP: box})
    await send(router)
    await send(router)

    taken = await box.drain("u1")
    assert len(taken) == 2
    # 取走之后不该再出现：轮询重复投递等于重复打扰。
    assert await box.inbox("u1") == []


async def test_drain_is_bounded_and_leaves_the_rest():
    box = InAppDelivery()
    router = ChannelRouter({Channel.IN_APP: box})
    for _ in range(3):
        await send(router)

    assert len(await box.drain("u1", limit=2)) == 2
    assert len(await box.inbox("u1")) == 1


async def test_inbox_is_per_user():
    box = InAppDelivery()
    await box.deliver(
        user_id="u1", character_id="linche", text="a", channel=Channel.IN_APP, at=at()
    )
    assert await box.inbox("u2") == []


async def test_inbox_is_bounded():
    """一个长期不打开应用的用户不该把内存吃满。"""
    box = InAppDelivery(history=2)
    for i in range(5):
        await box.deliver(
            user_id="u1",
            character_id="linche",
            text=f"m{i}",
            channel=Channel.IN_APP,
            at=at(),
        )
    assert [r.text for r in await box.inbox("u1")] == ["m3", "m4"]


async def test_successful_delivery_records_exactly_one_send():
    ledger = InMemorySendLedger()
    router = ChannelRouter({Channel.IN_APP: RecordingDelivery()}, recorder=ledger)

    await send(router)

    records = await ledger.records_for("u1")
    assert len(records) == 1
    assert records[0].trigger == "event:e1"
    assert records[0].channel == Channel.IN_APP


async def test_send_record_feeds_the_next_frequency_check():
    """记账不是为了好看：下一轮频控要从这里读。"""
    ledger = InMemorySendLedger()
    router = ChannelRouter({Channel.IN_APP: RecordingDelivery()}, recorder=ledger)
    prefs = InitiativePreferences()

    assert (await ledger.state_for("u1")).count_within(now=at(), days=1) == 0
    await send(router)
    assert (await ledger.state_for("u1")).count_within(now=at(), days=1) == 1
    assert prefs.max_per_day == 2


async def test_failed_delivery_records_nothing():
    """没发出去就不该占用户的额度。"""
    ledger = InMemorySendLedger()
    router = ChannelRouter(
        {Channel.IN_APP: RecordingDelivery(fail_times=1)}, recorder=ledger
    )

    with pytest.raises(DeliveryError):
        await send(router)

    assert await ledger.records_for("u1") == []


async def test_missing_channel_falls_back_to_in_app_not_silence():
    """电话没接上时，该出现在应用里；关系到用户的事不该因为通道缺失丢掉了。"""
    fallback = RecordingDelivery()
    ledger = InMemorySendLedger()
    router = ChannelRouter({Channel.IN_APP: fallback}, recorder=ledger)

    receipt = await send(router, channel=Channel.CALL)

    assert receipt.channel == Channel.IN_APP
    assert len(fallback.deliveries) == 1
    assert (await ledger.records_for("u1"))[0].channel == Channel.IN_APP


async def test_router_with_no_usable_channel_raises():
    router = ChannelRouter({})
    with pytest.raises(DeliveryError):
        await send(router)


async def test_receipt_serialises_for_the_client():
    box = InAppDelivery()
    receipt = await box.deliver(
        user_id="u1",
        character_id="linche",
        text="路上小心",
        channel=Channel.IN_APP,
        at=at(),
        meta={"reason": "ok"},
    )
    payload = receipt.to_json()
    assert payload["channel"] == "in_app"
    assert payload["at"].endswith("Z")
    assert payload["meta"] == {"reason": "ok"}


async def test_push_delivery_refuses_loudly_when_unconfigured():
    """接了一半的推送会在半夜发出半条消息，所以它必须明确失败。"""
    push = PushDelivery(environ={})
    assert push.configured is False
    with pytest.raises(NotImplementedError) as excinfo:
        await push.deliver(
            user_id="u1",
            character_id="linche",
            text="a",
            channel=Channel.PUSH,
            at=at(),
        )
    assert "COMPANION_FCM_PROJECT_ID" in str(excinfo.value)


async def test_push_delivery_does_not_fake_a_send_even_when_configured():
    push = PushDelivery(
        environ={
            PushDelivery.ENV_PROJECT_ID: "p",
            PushDelivery.ENV_CLIENT_EMAIL: "e@example.test",
            PushDelivery.ENV_PRIVATE_KEY: "k",
        }
    )
    assert push.configured is True
    with pytest.raises(NotImplementedError):
        await push.deliver(
            user_id="u1", character_id="linche", text="a", channel=Channel.PUSH, at=at()
        )
