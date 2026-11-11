"""主动性循环：一轮扫描里到底发不发。

这里的断言几乎全是「不该发」的方向，因为这一层错了的代价不对称：少发一条用户
不会有感觉，多发一条（尤其是半夜多发一条）这个功能就废了。

多数用例给调度器一份**宽松**偏好、给循环一份**默认**偏好，这是刻意的：策略本该
拦住的事，循环必须自己再拦一次。只测「策略拦住了」证明不了投递侧有第二道防线。
"""

from datetime import UTC, datetime, time, timedelta

import pytest

from companion.adapters.brain.fake import FakeBrain
from companion.ports.brain import BrainTurn
from companion.bootstrap.container import create_container
from companion.domain.proactive.models import Channel, InitiativePreferences
from companion.app.proactive.router import ChannelRouter
from companion.adapters.delivery.memory import InAppDelivery, InMemorySendLedger, RecordingDelivery
from companion.app.proactive.loop import InitiativeLoop
from companion.app.proactive.scheduler import InitiativeScheduler
from companion.app.proactive.loop import _channel_of, occurrence_key
from companion.domain.timeline.models import EventKind, TimelineEvent
from companion.domain.turn.trigger import Trigger, TriggerKind


def at(hour=10, minute=0, day=7):
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def permissive() -> InitiativePreferences:
    """什么都不拦：用来模拟「策略装配错了 / 上游放了行」。"""
    return InitiativePreferences(
        quiet_start=time(0, 0),
        quiet_end=time(0, 0),
        max_per_day=100,
        max_per_week=100,
    )


class ExplodingBrain:
    """回合直接抛错。用来证明「回合失败不发」不是靠空字符串碰巧成立的。"""

    def __init__(self) -> None:
        self.requests = 0

    async def start_turn(self, request):
        self.requests += 1
        raise RuntimeError("model unavailable")

    async def aclose(self) -> None:
        return None


class SilentBrain:
    """只发出情绪标签、没有可读文本的回合。"""

    def __init__(self, script=("[joy]",)) -> None:
        self._script = script

    async def start_turn(self, request):
        async def tokens():
            for chunk in self._script:
                yield chunk

        async def cancel() -> None:
            return None

        return BrainTurn(tokens=tokens(), cancel=cancel, turn_id="t-silent")

    async def aclose(self) -> None:
        return None


def _loader(prefs: InitiativePreferences):
    async def load(user_id: str) -> InitiativePreferences:
        return prefs

    return load


async def build(*, brain=None, scheduler_prefs=None, loop_prefs=None, fail_times=0):
    """装配一条真实链路：真容器 + 真中间件 + 真时间线，只换投递与主脑。"""
    container = create_container(brain=brain)
    ledger = InMemorySendLedger()
    delivery = RecordingDelivery(fail_times=fail_times)
    router = ChannelRouter({Channel.IN_APP: delivery}, recorder=ledger)

    scheduler = InitiativeScheduler(
        timeline=container.timeline,
        preferences_loader=_loader(scheduler_prefs or permissive()),
        state_loader=ledger.state_for,
    )
    loop = InitiativeLoop(
        scheduler=scheduler,
        conversation=container.conversation,
        router=router,
        preferences_loader=_loader(loop_prefs or InitiativePreferences()),
        state_loader=ledger.state_for,
    )
    return container, loop, delivery, ledger


async def seed(container, *, event_id="e1", kind=EventKind.INTERVIEW, when=None, user_id="u1"):
    event = TimelineEvent(
        id=event_id,
        user_id=user_id,
        kind=kind,
        # 每件事标题不同：时间线按「标题 + 当地日期」合并同一件事，同名同日的两条会变成一条
        title=f"产品经理面试-{event_id}",
        at=when or at(hour=10, minute=3),
        source_character_id="linche",
        confidence=0.9,
    )
    return await container.timeline.add(event)


async def test_due_event_becomes_one_message_and_one_record():
    container, loop, delivery, ledger = await build()
    await seed(container)

    result = await loop.run_once(at())

    assert len(result.delivered) == 1
    assert len(delivery.deliveries) == 1
    assert delivery.deliveries[0].channel == Channel.IN_APP
    assert delivery.deliveries[0].character_id == "linche"
    assert delivery.deliveries[0].text  # 有真的内容，不是空串
    records = await ledger.records_for("u1")
    assert len(records) == 1
    assert records[0].trigger == "event:e1"


async def test_second_cycle_with_the_same_event_delivers_nothing():
    """扫描窗口是分钟级的，同一个事件会被扫到好几次。重复投递在这里挡住。"""
    container, loop, delivery, ledger = await build()
    await seed(container)

    await loop.run_once(at())
    second = await loop.run_once(at(minute=1))

    assert second.delivered == []
    assert len(delivery.deliveries) == 1
    assert len(await ledger.records_for("u1")) == 1
    assert ("event:e1", "duplicate") in second.skipped


async def test_delivery_failure_is_not_retried():
    """补发的消息比漏发的更烦人：失败就放弃，下一轮也不重来。"""
    container, loop, delivery, ledger = await build(fail_times=1)
    await seed(container)

    first = await loop.run_once(at())
    assert first.delivered == []
    assert first.failed and first.failed[0][1] == "delivery:DeliveryError"
    assert await ledger.records_for("u1") == []

    second = await loop.run_once(at(minute=1))
    # 没有重试：投递端口总共只被调用过一次。
    assert delivery.attempts == 1
    assert second.delivered == []


async def test_a_failing_turn_never_delivers_half_a_sentence():
    brain = ExplodingBrain()
    container, loop, delivery, ledger = await build(brain=brain)
    await seed(container)

    result = await loop.run_once(at())

    assert brain.requests == 1
    assert result.delivered == []
    assert result.failed and result.failed[0][1] == "turn:RuntimeError"
    assert delivery.attempts == 0
    # 也不记账：没发出去就不该占用户的额度。
    assert await ledger.records_for("u1") == []


async def test_a_turn_with_no_text_is_not_delivered():
    """模型只吐了情绪标签：没有可读内容，就不发一条空消息。"""
    container, loop, delivery, _ = await build(brain=SilentBrain())
    await seed(container)

    result = await loop.run_once(at())

    assert result.delivered == []
    assert ("event:e1", "empty_turn") in result.skipped
    assert delivery.attempts == 0


@pytest.mark.parametrize("hour", [23, 0, 3, 7])
async def test_quiet_hours_are_honoured_even_if_the_decision_says_yes(hour):
    """策略放了行，循环仍要在投递前看一眼时间——半夜发出的推送收不回来。"""
    container, loop, delivery, _ = await build(loop_prefs=InitiativePreferences())
    await seed(container, when=at(hour=hour, minute=3))

    result = await loop.run_once(at(hour=hour, minute=0))

    assert result.delivered == []
    assert delivery.attempts == 0
    assert ("event:e1", "quiet_hours") in result.skipped


async def test_quiet_hours_skip_is_not_remembered_as_delivered():
    """安静时段跳过 ≠ 处理过：时段结束后，这件事仍该出现在用户早上打开应用时。"""
    container, loop, delivery, _ = await build()
    await seed(container, when=at(hour=8, minute=2))

    quiet = await loop.run_once(at(hour=7, minute=59))
    assert quiet.delivered == []
    assert ("event:e1", "quiet_hours") in quiet.skipped

    awake = await loop.run_once(at(hour=8, minute=0))
    assert len(awake.delivered) == 1
    assert delivery.attempts == 1


async def test_two_events_in_one_cycle_respect_the_daily_cap():
    """一轮里三件事到期，不能三条一起发：频控要复检**上一次投递之后**的状态。"""
    container, loop, delivery, ledger = await build()
    await seed(container, event_id="e1")
    await seed(container, event_id="e2")
    await seed(container, event_id="e3")

    result = await loop.run_once(at())

    assert len(result.delivered) == 2  # 默认 max_per_day=2
    assert len(delivery.deliveries) == 2
    assert len(await ledger.records_for("u1")) == 2
    assert [reason for _, reason in result.skipped].count("daily_cap") == 1


async def test_paused_user_is_not_disturbed():
    container, loop, delivery, _ = await build(
        loop_prefs=InitiativePreferences(paused_until=at(hour=12))
    )
    await seed(container)

    result = await loop.run_once(at())

    assert result.delivered == []
    assert delivery.attempts == 0
    assert ("event:e1", "paused") in result.skipped


async def test_in_app_inbox_holds_what_was_delivered():
    """端上 v1 就是这么拿到的：轮询收件箱。"""
    box = InAppDelivery()
    container = create_container()
    await seed(container)

    scheduler = InitiativeScheduler(
        timeline=container.timeline, preferences_loader=_loader(permissive())
    )
    loop = InitiativeLoop(
        scheduler=scheduler,
        conversation=container.conversation,
        router=ChannelRouter({Channel.IN_APP: box}),
        preferences_loader=_loader(InitiativePreferences()),
    )

    await loop.run_once(at())

    pending = await box.inbox("u1")
    assert len(pending) == 1
    assert pending[0].meta["trigger"] == "event_due"
    assert pending[0].meta["event_id"] == "e1"


async def test_seen_records_are_pruned_so_memory_does_not_grow_forever():
    container, loop, _, _ = await build()
    await seed(container)
    await loop.run_once(at())
    assert loop._seen  # noqa: SLF001

    await loop.run_once(at() + timedelta(days=2))
    assert loop._seen == {}  # noqa: SLF001


async def test_a_second_occurrence_of_a_recurring_event_is_not_a_duplicate():
    """同一个 id、下一次发生：身份不同，该发。否则一个生日只提醒过一次就永远哑了。"""
    first = Trigger(
        kind=TriggerKind.EVENT_DUE,
        user_id="u1",
        character_id="linche",
        payload={"event_id": "birthday", "at": at(day=7).isoformat()},
        origin="event:birthday",
    )
    second = Trigger(
        kind=TriggerKind.EVENT_DUE,
        user_id="u1",
        character_id="linche",
        payload={"event_id": "birthday", "at": at(day=7).replace(year=2027).isoformat()},
        origin="event:birthday",
    )

    assert occurrence_key(first, at()) != occurrence_key(second, at())
    # 同一件事被扫两次，身份必须一致。
    assert occurrence_key(first, at()) == occurrence_key(first, at(minute=4))


async def test_a_trigger_without_an_event_id_is_at_most_once_a_day():
    """问候这类触发没有事件 id，退化成「用户 + 来源 + 日期」。"""
    greeting = Trigger(
        kind=TriggerKind.SCHEDULE,
        user_id="u1",
        character_id="linche",
        origin="schedule:morning",
    )

    assert occurrence_key(greeting, at(hour=9)) == occurrence_key(greeting, at(hour=11))
    assert occurrence_key(greeting, at(day=7)) != occurrence_key(greeting, at(day=8))


async def test_unknown_channel_falls_back_instead_of_raising():
    """载荷里的通道名认不出时退回应用内：它不会在半夜响铃。"""
    trigger = Trigger(
        kind=TriggerKind.EVENT_DUE,
        user_id="u1",
        character_id="linche",
        payload={"channel": "telepathy"},
        origin="event:e1",
    )
    assert _channel_of(trigger) == Channel.IN_APP


async def test_fake_brain_path_is_exercised():
    """确认上面的断言不是靠空语料侥幸通过：默认主脑确实吐得出文本。"""
    brain = FakeBrain(["面试加油。"])
    container, loop, delivery, _ = await build(brain=brain)
    await seed(container)
    await loop.run_once(at())
    assert delivery.deliveries[0].text == "面试加油。"
