"""SqlTimelineStore.due_between：主动开口的调度器扫描入口。"""

from datetime import UTC, datetime, timedelta

from companion.service.timeline.sql import SqlTimelineStore
from companion.service.timeline.models import EventKind, EventStatus, TimelineEvent

# 相对当前时间：事件已过去时 next_at_utc 为空，固定的历史日期会让用例悄悄失效
NOW = datetime.now(UTC).replace(second=0, microsecond=0) + timedelta(hours=1)


def _event(eid: str, *, minutes: int, user="1002", reminder_id=None, status=EventStatus.SCHEDULED):
    return TimelineEvent(id=eid, user_id=user, kind=EventKind.INTERVIEW, title=f"面试-{eid}",
                         at=NOW + timedelta(minutes=minutes), source_character_id="linche",
                         reminder_id=reminder_id, status=status)


async def _ids(store, start_min, end_min):
    got = await store.due_between(start=NOW + timedelta(minutes=start_min), end=NOW + timedelta(minutes=end_min))
    return {e.id for e in got}


async def test_only_events_inside_the_window_are_due(sqlite_engine):
    store = SqlTimelineStore(sqlite_engine)
    for eid, m in [("before", -10), ("inside", 3), ("edge", 5), ("after", 30)]:
        await store.upsert(_event(eid, minutes=m))
    assert await _ids(store, 0, 5) == {"inside", "edge"}


async def test_events_of_every_user_are_scanned(sqlite_engine):
    store = SqlTimelineStore(sqlite_engine)
    await store.upsert(_event("a", minutes=2, user="1002"))
    await store.upsert(_event("b", minutes=2, user="1003"))
    assert await _ids(store, 0, 5) == {"a", "b"}


async def test_events_with_a_reminder_are_left_to_the_reminder_dispatcher(sqlite_engine):
    store = SqlTimelineStore(sqlite_engine)
    await store.upsert(_event("plain", minutes=2))
    await store.upsert(_event("reminded", minutes=2, reminder_id=77))
    assert await _ids(store, 0, 5) == {"plain"}


async def test_finished_or_cancelled_events_are_not_due(sqlite_engine):
    store = SqlTimelineStore(sqlite_engine)
    await store.upsert(_event("done", minutes=2, status=EventStatus.DONE))
    await store.upsert(_event("live", minutes=2))
    assert await _ids(store, 0, 5) == {"live"}


async def test_the_scan_is_bounded(sqlite_engine):
    store = SqlTimelineStore(sqlite_engine)
    for i in range(5):
        await store.upsert(_event(f"e{i}", minutes=1, user=str(2000 + i)))
    got = await store.due_between(start=NOW, end=NOW + timedelta(minutes=5), limit=3)
    assert len(got) == 3
