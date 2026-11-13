"""主动消息端到端：到期事件 → 主动开口循环 → 收件箱（Postgres 存储）→ 客户端取走。

用内存 SQLite 上的真实 SQL 存储（时间线、收件箱、频控账本、偏好）跑完整链路，
所以这条链路在任何机器上都会真正执行，不会因为没配外部数据库而被跳过。
验证：收件箱只给本人、取走即清空、安静时段不发、同一件事只发一次。
"""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.proactive.store import SqlDelivery, SqlPreferencesStore, SqlSendLedger
from companion.timeline.sql import SqlTimelineStore
from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.http.routers import inbox as inbox_router
from companion.proactive.loop import InitiativeLoop
from companion.proactive.router import ChannelRouter
from companion.proactive.scheduler import InitiativeScheduler
from companion.proactive.models import Channel
from companion.timeline.models import EventKind, TimelineEvent

ALICE, BOB = 1002, 1003


def _next(hour: int, minute: int = 0) -> datetime:
    """下一个（严格在未来的）UTC 整点时刻。

    事件一旦落在过去，库里的 next_at_utc 就是空，调度器根本不会扫到它——
    用今天的固定钟点会在下午让用例悄悄变成“什么都没扫到所以什么都没发”。
    """
    now = datetime.now(UTC)
    t = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return t if t > now + timedelta(minutes=30) else t + timedelta(days=1)


class Speaker:
    async def __call__(self, trigger) -> str:
        return "[joy]面试加油，我在这儿陪你。"


async def _build(engine):
    timeline = SqlTimelineStore(engine)
    prefs, delivery, ledger = SqlPreferencesStore(engine), SqlDelivery(engine), SqlSendLedger(engine)
    loop = InitiativeLoop(
        scheduler=InitiativeScheduler(timeline=timeline, preferences_loader=prefs.load, state_loader=ledger.state_for),
        speak=Speaker(), router=ChannelRouter({Channel.IN_APP: delivery}, recorder=ledger),
        preferences_loader=prefs.load, state_loader=ledger.state_for)
    app = FastAPI()
    app.include_router(inbox_router.build_router(inbox=inbox_router.InboxApi(delivery=delivery),
                                                 current_user=build_current_user(AllowAllVerifier())))
    return timeline, loop, app


def _seed(timeline, user: int, when: datetime, eid="e1"):
    return timeline.upsert(TimelineEvent(id=eid, user_id=str(user), kind=EventKind.INTERVIEW, title=f"产品经理面试-{eid}",   # 时间线按「标题 + 当地日期」合并同一件事，标题要不同
                                         at=when, source_character_id="linche", confidence=0.9))


def _as(user: int) -> dict:
    return {"Authorization": f"Bearer {user}"}


async def test_due_event_reaches_the_owner_inbox_once_and_is_drained(sqlite_engine):
    timeline, loop, app = await _build(sqlite_engine)
    now = _next(12)   # 中午：不在默认安静时段
    await _seed(timeline, ALICE, now + timedelta(minutes=3))

    result = await loop.run_once(now)
    assert len(result.delivered) == 1, result

    with TestClient(app) as client:
        first = client.get("/v1/inbox", headers=_as(ALICE)).json()
        assert len(first) == 1
        assert first[0]["text"] == "面试加油，我在这儿陪你。"   # 情绪标签已剥掉
        assert first[0]["trigger"] == "event_due" and first[0]["channel"] == "in_app"
        # 取走即清空
        assert client.get("/v1/inbox", headers=_as(ALICE)).json() == []


async def test_inbox_is_private_to_the_owner(sqlite_engine):
    timeline, loop, app = await _build(sqlite_engine)
    now = _next(12)
    await _seed(timeline, ALICE, now + timedelta(minutes=3))
    await loop.run_once(now)

    with TestClient(app) as client:
        assert client.get("/v1/inbox", headers=_as(BOB)).json() == []
        assert len(client.get("/v1/inbox", headers=_as(ALICE)).json()) == 1


async def test_quiet_hours_produce_no_inbox_message(sqlite_engine):
    timeline, loop, app = await _build(sqlite_engine)
    now = _next(23, 25)
    await _seed(timeline, ALICE, now + timedelta(minutes=3))

    result = await loop.run_once(now)

    assert result.delivered == []
    # 确实扫到了这件事、并且是被安静时段拦下的，而不是什么都没扫到。
    # 调度器的策略先拦（键是用户 id）；循环在投递前还有第二道（键是事件来源），两处都算数。
    assert ("1002", "quiet_hours") in result.skipped or ("event:e1", "quiet_hours") in result.skipped, result
    with TestClient(app) as client:
        assert client.get("/v1/inbox", headers=_as(ALICE)).json() == []


async def test_the_same_event_is_not_sent_twice_across_rounds(sqlite_engine):
    timeline, loop, app = await _build(sqlite_engine)
    now = _next(12)
    await _seed(timeline, ALICE, now + timedelta(minutes=3))

    await loop.run_once(now)
    second = await loop.run_once(now + timedelta(minutes=1))

    assert second.delivered == []
    with TestClient(app) as client:
        assert len(client.get("/v1/inbox", headers=_as(ALICE)).json()) == 1


async def test_the_daily_cap_survives_a_new_loop_instance(sqlite_engine):
    """频控账本在库里：换一个循环实例（相当于重启 / 另一个进程）后额度仍然算数。"""
    timeline, loop, _ = await _build(sqlite_engine)
    now = _next(12)
    for i in range(3):
        await _seed(timeline, ALICE, now + timedelta(minutes=2 + i), eid=f"e{i}")
    assert len((await loop.run_once(now)).delivered) == 2   # 默认 max_per_day=2

    _, fresh, _ = await _build(sqlite_engine)
    again = await fresh.run_once(now + timedelta(minutes=1))
    assert again.delivered == []
    assert any(reason == "daily_cap" for _, reason in again.skipped)
