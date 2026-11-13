"""事件时间线：存储、重复事件、抽取。

时间线是「她记得你要面试」的基础，所以两件事必须对：
- 重复事件（生日）每年都能被扫到；
- 用户隔离（拿别人的 id 也查不到、改不了）。
"""

from datetime import UTC, datetime, timedelta

import pytest

from companion.service.timeline.models import EventKind, EventStatus, Recurrence, TimelineEvent
from companion.service.timeline.memory import InMemoryTimeline
from companion.service.timeline.extraction import parse_events


def event(**kw):
    base = dict(
        id="e1",
        user_id="u1",
        kind=EventKind.INTERVIEW,
        title="面试",
        at=datetime(2026, 11, 20, 14, 0, tzinfo=UTC),
    )
    base.update(kw)
    return TimelineEvent(**base)


async def test_add_and_list_returns_future_events_sorted():
    store = InMemoryTimeline()
    # 以真实的「现在」为基准：用固定的 2026-11-01 会因为时间推移变成过去。
    now = datetime.now(UTC)
    await store.add(event(id="b", at=now + timedelta(days=10)))
    await store.add(event(id="a", at=now + timedelta(days=3)))
    items = await store.list_for_user("u1")
    assert [e.id for e in items] == ["a", "b"]


async def test_list_excludes_past_by_default():
    store = InMemoryTimeline()
    await store.add(event(at=datetime(2020, 1, 1, tzinfo=UTC)))
    assert await store.list_for_user("u1") == []
    assert len(await store.list_for_user("u1", include_past=True)) == 1


async def test_user_isolation_on_read_and_write():
    store = InMemoryTimeline()
    await store.add(event(id="e1", user_id="u1"))
    assert await store.list_for_user("u2") == []
    # 拿别人的 event id 也改不了、删不掉。
    assert await store.update_status("u2", "e1", EventStatus.CANCELLED) is False
    assert await store.delete_one("u2", "e1") is False
    assert len(await store.list_for_user("u1", include_past=True)) == 1


async def test_delete_user_removes_everything():
    store = InMemoryTimeline()
    await store.add(event(id="e1", user_id="u1"))
    await store.add(event(id="e2", user_id="u1", title="复诊"))
    await store.add(event(id="e3", user_id="u2"))
    assert await store.delete_user("u1") == 2
    assert await store.list_for_user("u1", include_past=True) == []
    assert len(await store.list_for_user("u2", include_past=True)) == 1


async def test_due_between_finds_event_in_window():
    store = InMemoryTimeline()
    at = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)
    await store.add(event(at=at))
    due = await store.due_between(start=at - timedelta(minutes=5), end=at + timedelta(minutes=5))
    assert len(due) == 1


async def test_due_between_uses_next_occurrence_for_yearly_events():
    """1990 年的生日必须在今年被扫到——只看原始 at 会永远扫不到。"""
    store = InMemoryTimeline()
    await store.add(
        event(at=datetime(1990, 11, 20, 9, 0, tzinfo=UTC), recurrence=Recurrence.YEARLY)
    )
    due = await store.due_between(
        start=datetime(2026, 11, 20, 8, 0, tzinfo=UTC),
        end=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
    )
    assert len(due) == 1


def test_next_occurrence_is_bounded_for_old_dates():
    """有界循环：一个很早的月度事件不该让这里转上千万次。"""
    old = event(at=datetime(1990, 1, 1, tzinfo=UTC), recurrence=Recurrence.MONTHLY)
    nxt = old.next_occurrence(after=datetime(2026, 1, 1, tzinfo=UTC))
    assert nxt is not None and nxt.year >= 2026


def test_next_occurrence_none_for_cancelled():
    cancelled = event(status=EventStatus.CANCELLED)
    assert cancelled.next_occurrence(after=datetime(2026, 1, 1, tzinfo=UTC)) is None


def test_parse_events_reads_json_inside_a_fence():
    raw = """```json
[{"kind":"interview","title":"字节面试","at":"2026-11-20T14:00:00+08:00",
  "recurrence":"none","confidence":0.9}]
```"""
    events = parse_events(raw, user_id="u1", character_id="linche", message_id="m1")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "字节面试"
    assert ev.kind == EventKind.INTERVIEW
    assert ev.confidence == pytest.approx(0.9)
    assert ev.source_character_id == "linche"


def test_parse_events_drops_entries_without_time_or_title():
    raw = '[{"title":"没时间的"},{"at":"2026-11-20T14:00:00+08:00"},{"title":"好的","at":"2026-11-20T14:00:00+08:00"}]'
    events = parse_events(raw, user_id="u1", character_id="c", message_id="m")
    assert [e.title for e in events] == ["好的"]


def test_parse_events_tolerates_garbage():
    for raw in ("", "not json", "{}", "[]", "[1,2,3]"):
        assert parse_events(raw, user_id="u", character_id="c", message_id="m") == []


def test_parse_events_unknown_kind_falls_back_to_other():
    raw = '[{"kind":"外星事件","title":"x","at":"2026-11-20T14:00:00+08:00"}]'
    events = parse_events(raw, user_id="u", character_id="c", message_id="m")
    assert events[0].kind is EventKind.OTHER
