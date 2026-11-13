"""主动消息三块存储（偏好 / 收件箱 / 账本）落库后的行为。

这三个之前都在进程内，所以每条用例都问同一个问题：**换一个进程（新引擎、新实例）还看不看得见？**
如果只在同一实例上读写，内存版也能通过，测试就没有意义。
"""

import asyncio
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

# 每个用例用自己的用户 id：全量跑时别的用例（以及上一次运行）留下的行不能被看见。
# 固定 id 会让「重启后还在」这类断言变成功夫在诗外——它可能是上一次运行留下的。
_RUN = int(time.time()) % 100000


def _uid(n: int) -> str:
    return str(9_000_000_000 + _RUN * 1000 + n)

URL = (os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", ""))
pytestmark = pytest.mark.skipif(not URL, reason="COMPANION_TEST_DATABASE_URL not set")


def run(coro):
    return asyncio.run(coro)


async def _fresh(url=URL):
    """新建一套引擎与实例，模拟进程重启。"""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url, pool_pre_ping=True)
    return engine


async def _with(store_factory, fn):
    engine = await _fresh()
    try:
        return await fn(store_factory(engine))
    finally:
        await engine.dispose()


def test_preferences_survive_a_restart():
    from companion.proactive.store import SqlPreferencesStore

    async def go():
        # 第一个进程：关掉主动消息并暂停到明天
        async def first(store):
            paused = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
            return await store.save(_uid(1), {"events_enabled": False, "greetings_enabled": True,
                                             "max_per_day": 1, "paused_until": paused})

        saved = await _with(SqlPreferencesStore, first)
        assert saved.events_enabled is False and saved.max_per_day == 1

        # 第二个进程：必须读到同样的值，而不是回到默认（events 真、greetings 假）
        async def second(store):
            return await store.load(_uid(1))

        loaded = await _with(SqlPreferencesStore, second)
        assert loaded.events_enabled is False
        assert loaded.greetings_enabled is True
        assert loaded.max_per_day == 1
        assert loaded.paused_until is not None, "暂停时间丢了会让用户在暂停期间收到主动消息"

    run(go())


def test_preferences_without_a_row_return_defaults_and_do_not_create_one():
    from companion.proactive.store import SqlPreferencesStore

    async def go():
        engine = await _fresh()
        try:
            store = SqlPreferencesStore(engine)
            prefs = await store.load(_uid(2))
            assert prefs.events_enabled is True and prefs.greetings_enabled is False
            assert prefs.max_per_day == 2
        finally:
            await engine.dispose()

    run(go())


def test_quiet_hours_accept_hh_mm_strings_and_round_trip():
    from companion.proactive.store import SqlPreferencesStore

    async def go():
        engine = await _fresh()
        try:
            store = SqlPreferencesStore(engine)
            await store.save(_uid(3), {"quiet_start": "22:30", "quiet_end": "07:15"})
        finally:
            await engine.dispose()

        async def read(store):
            return await store.load(_uid(3))

        prefs = await _with(SqlPreferencesStore, read)
        assert prefs.quiet_start.hour == 22 and prefs.quiet_start.minute == 30
        assert prefs.quiet_end.hour == 7 and prefs.quiet_end.minute == 15

    run(go())


def test_inbox_message_is_still_there_after_a_restart():
    from companion.proactive.store import SqlDelivery
    from companion.proactive.delivery_port import Channel

    message = "你昨天说的面试，今天怎么样？"

    async def send(store):
        return await store.deliver(user_id=_uid(4), character_id="linche", text=message,
                                   channel=Channel.IN_APP, at=datetime.now(UTC),
                                   meta={"trigger": "reminder"})

    receipt = run(_with(SqlDelivery, send))
    assert receipt.id.startswith("inapp-")

    async def read(store):
        return await store.inbox(_uid(4))

    inbox = run(_with(SqlDelivery, read))
    assert [r.text for r in inbox] == [message]
    assert inbox[0].meta.get("trigger") == "reminder"


def test_drain_marks_read_and_does_not_delete():
    """取走后不再出现在收件箱，但记录保留，事后能对账「她到底发过什么」。"""
    from companion.proactive.store import SqlDelivery
    from companion.proactive.delivery_port import Channel

    async def go():
        engine = await _fresh()
        try:
            store = SqlDelivery(engine)
            for i in range(3):
                await store.deliver(user_id=_uid(5), character_id="linche", text=f"m{i}",
                                    channel=Channel.IN_APP, at=datetime.now(UTC) + timedelta(seconds=i))
            taken = await store.drain(_uid(5), limit=2)
            assert [t.text for t in taken] == ["m0", "m1"]
            rest = await store.inbox(_uid(5))
            assert [t.text for t in rest] == ["m2"]
        finally:
            await engine.dispose()

    run(go())


def test_one_users_inbox_never_leaks_into_anothers():
    from companion.proactive.store import SqlDelivery
    from companion.proactive.delivery_port import Channel

    async def go():
        engine = await _fresh()
        try:
            store = SqlDelivery(engine)
            await store.deliver(user_id=_uid(6), character_id="linche", text="for 7005",
                                channel=Channel.IN_APP, at=datetime.now(UTC))
            assert await store.inbox(_uid(7)) == []
        finally:
            await engine.dispose()

    run(go())


def test_send_ledger_counts_across_restarts_so_frequency_limits_hold():
    """频控是「每天 2 次」。两个进程各发一次，第三个进程必须看到已经 2 次。"""
    from companion.proactive.store import SqlSendLedger
    from companion.proactive.models import SendRecord
    from companion.proactive.delivery_port import Channel

    now = datetime.now(UTC)

    async def record(store):
        await store.record(_uid(8), SendRecord(at=now, channel=Channel.IN_APP, trigger="reminder"))

    run(_with(SqlSendLedger, record))
    run(_with(SqlSendLedger, record))

    async def read(store):
        return await store.state_for(_uid(8))

    state = run(_with(SqlSendLedger, read))
    assert state.count_within(now=now, days=1) == 2


def test_send_ledger_ignores_records_outside_the_window():
    from companion.proactive.store import SqlSendLedger
    from companion.proactive.models import SendRecord
    from companion.proactive.delivery_port import Channel

    now = datetime.now(UTC)

    async def go():
        engine = await _fresh()
        try:
            store = SqlSendLedger(engine)
            await store.record(_uid(9), SendRecord(at=now - timedelta(days=10), channel=Channel.IN_APP, trigger="old"))
            await store.record(_uid(9), SendRecord(at=now, channel=Channel.IN_APP, trigger="new"))
            state = await store.state_for(_uid(9))
            assert state.count_within(now=now, days=1) == 1
            assert state.count_within(now=now, days=30) == 2
        finally:
            await engine.dispose()

    run(go())
