"""合规 SQL 实现的行为（sqlite_engine 夹具，见 conftest）。

touch_usage 曾经只测内存实现：换成 SqlComplianceStore 后「同一用户第二次活跃」
起 naive-aware 相减抛 TypeError，被调用方的 fail-open 吞成一条 warning，
生产上每条消息刷一次却没人看见。这些用例钉住的是**SQL 实现本身**。
"""

from datetime import UTC, datetime, timedelta

import pytest

from companion.service.compliance.port import REMIND_AFTER_MINUTES, SPAN_GAP_MINUTES
from companion.service.compliance.sql import SqlComplianceStore


@pytest.fixture
def store(sqlite_engine):
    return SqlComplianceStore(sqlite_engine)


async def test_touch_usage_survives_a_second_activity_for_the_same_user(store):
    """第一次成功、第二次起失败——TypeError(naive - aware) 的回归钉子。"""
    base = datetime.now(UTC)
    first = await store.touch_usage(owner_id=1, now=base)
    assert first.span_minutes == 0 and not first.should_remind

    later = await store.touch_usage(owner_id=1, now=base + timedelta(minutes=5))
    assert later.span_minutes == 5
    assert not later.should_remind

    # 连续第三次：每次都要能读回上一行并做时间差
    await store.touch_usage(owner_id=1, now=base + timedelta(minutes=10))


async def test_touch_usage_starts_a_new_span_after_the_gap(store):
    base = datetime.now(UTC)
    await store.touch_usage(owner_id=1, now=base)
    after_gap = await store.touch_usage(owner_id=1, now=base + timedelta(minutes=SPAN_GAP_MINUTES + 1))
    assert after_gap.span_minutes == 0


async def test_touch_usage_reminds_once_after_the_threshold(store):
    # 提醒只能在「连续使用」里触发：两次活跃间隔超过 SPAN_GAP_MINUTES 就重开一段，
    # 所以直接跳到 +120 分钟不会提醒（那是新的一段）。每 30 分钟活跃一次才连成段。
    base = datetime.now(UTC)
    await store.touch_usage(owner_id=1, now=base)
    due = None
    for minutes in (30, 60, 90, REMIND_AFTER_MINUTES):
        due = await store.touch_usage(owner_id=1, now=base + timedelta(minutes=minutes))
    assert due is not None and due.should_remind
    # 提醒过就闭嘴，直到下一段
    again = await store.touch_usage(owner_id=1, now=base + timedelta(minutes=REMIND_AFTER_MINUTES + 1))
    assert not again.should_remind


async def test_touch_usage_accepts_naive_input_as_utc(store):
    """调用方理论上总是给 aware；naive 也不能炸（按 UTC 解释）。"""
    naive = datetime.now(UTC).replace(tzinfo=None)
    state = await store.touch_usage(owner_id=7, now=naive)
    assert state.span_minutes == 0
