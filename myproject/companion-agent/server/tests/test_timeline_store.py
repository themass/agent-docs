"""时间线持久化：SQL 与内存实现同一套语义（chat-agent-timeline-design.md）。

需要 COMPANION_TEST_DATABASE_URL 才会跑 SQL 部分（memory_schema 夹具负责建表）。
"""

import os
import random
from datetime import UTC, datetime, timedelta

import pytest

from companion.service.timeline.memory import InMemoryTimeline
from companion.service.timeline.models import (
    EventKind,
    EventOrigin,
    EventStatus,
    Recurrence,
    TimelineEvent,
    dedupe_key,
)

URL = os.environ.get("COMPANION_TEST_DATABASE_URL", "")


@pytest.fixture(params=["memory", "sql"])
async def store(request, memory_schema):
    if request.param == "memory":
        yield InMemoryTimeline()
        return
    if not URL:
        pytest.skip("COMPANION_TEST_DATABASE_URL not set")
    from sqlalchemy.ext.asyncio import create_async_engine

    from companion.service.timeline.sql import SqlTimelineStore

    engine = create_async_engine(URL, pool_pre_ping=True)
    try:
        yield SqlTimelineStore(engine)
    finally:
        await engine.dispose()


def owner() -> str:
    return str(random.randint(10**8, 10**9))


def event(user, **kw):
    base = dict(id="", user_id=user, kind=EventKind.INTERVIEW, title="产品经理面试",
                at=datetime.now(UTC) + timedelta(days=3), source_character_id="linche")
    base.update(kw)
    return TimelineEvent(**base)


async def test_upsert_merges_the_same_event(store):
    user = owner()
    first = await store.upsert(event(user, source_message_id="m1", confidence=0.6, origin=EventOrigin.TOOL))
    again = await store.upsert(event(user, source_message_id="m1", confidence=0.9, origin=EventOrigin.EXTRACTED))
    assert again.id == first.id                       # 同一件事只留一条，id 不变
    rows = await store.list_for_owner(owner_id=user, include_past=True)
    assert len(rows) == 1
    assert rows[0].confidence == 0.9                  # 更可信的信息补全进来


async def test_same_event_in_another_role_is_separate(store):
    user = owner()
    await store.upsert(event(user, source_character_id="linche"))
    await store.upsert(event(user, source_character_id="sudai"))
    assert len(await store.list_for_owner(owner_id=user, include_past=True, role_id="linche")) == 1
    assert len(await store.list_for_owner(owner_id=user, include_past=True, role_id="sudai")) == 1


async def test_upcoming_and_recent_past_split_by_role(store):
    user = owner()
    now = datetime.now(UTC)
    await store.upsert(event(user, title="明天的面试", at=now + timedelta(days=1)))
    await store.upsert(event(user, title="昨天复诊", at=now - timedelta(days=1), kind=EventKind.APPOINTMENT))
    await store.upsert(event(user, title="很远的旅行", at=now + timedelta(days=40), kind=EventKind.TRIP))
    await store.upsert(event(user, title="苏黛那边的事", at=now + timedelta(days=1), source_character_id="sudai"))

    upcoming = await store.upcoming(owner_id=user, role_id="linche", now=now, horizon=timedelta(days=14))
    assert [e.title for e in upcoming] == ["明天的面试"]
    past = await store.recent_past(owner_id=user, role_id="linche", now=now, window=timedelta(days=2))
    assert [e.title for e in past] == ["昨天复诊"]


async def test_status_and_deletion_need_ownership(store):
    user, other = owner(), owner()
    saved = await store.upsert(event(user))
    assert await store.set_status(owner_id=other, public_id=saved.id, status=EventStatus.DONE) is False
    assert await store.set_status(owner_id=user, public_id=saved.id, status=EventStatus.DONE) is True
    assert await store.upcoming(owner_id=user, role_id="linche", now=datetime.now(UTC),
                                horizon=timedelta(days=14)) == []
    assert await store.delete(owner_id=other, public_id=saved.id) is False
    assert await store.delete(owner_id=user, public_id=saved.id) is True


async def test_edit_or_delete_of_a_message_makes_its_events_stale(store):
    user = owner()
    from_message = await store.upsert(event(user, title="面试", source_message_id="m7"))
    manual = await store.upsert(event(user, title="体检", source_message_id="m7", origin=EventOrigin.MANUAL))
    assert await store.mark_stale_for_source(owner_id=user, message_id="m7") == 1   # 手动添加的不受影响
    assert [e.status for e in await store.by_source(owner_id=user, message_id="m7")] == \
        [EventStatus.STALE, EventStatus.SCHEDULED]
    assert (await store.get(owner_id=user, public_id=from_message.id)).status == EventStatus.STALE
    assert (await store.get(owner_id=user, public_id=manual.id)).status == EventStatus.SCHEDULED
    # 重新提到同一件事：恢复为 scheduled
    revived = await store.upsert(event(user, title="面试", source_message_id="m8"))
    assert revived.id == from_message.id and revived.status == EventStatus.SCHEDULED


async def test_delete_for_session_keeps_manual_events(store):
    user = owner()
    await store.upsert(event(user, title="会话里说的", session_id=42))
    await store.upsert(event(user, title="记忆页加的", session_id=42, origin=EventOrigin.MANUAL))
    assert await store.delete_for_session(owner_id=user, session_id=42) == 1
    assert [e.title for e in await store.list_for_owner(owner_id=user, include_past=True)] == ["记忆页加的"]


def test_dedupe_key_ignores_spacing_and_punctuation():
    at = datetime(2026, 11, 20, 14, 0, tzinfo=UTC)
    assert dedupe_key("面试", at) == dedupe_key(" 面试！", at + timedelta(hours=3))
    assert dedupe_key("面试", at) != dedupe_key("面试", at + timedelta(days=1))


def test_monthly_recurrence_does_not_drift_from_the_31st():
    at = datetime(2026, 1, 31, 9, 0, tzinfo=UTC)
    e = TimelineEvent(id="", user_id="1", kind=EventKind.OTHER, title="房租", at=at, recurrence=Recurrence.MONTHLY)
    assert e.next_occurrence(after=datetime(2026, 2, 1, tzinfo=UTC)) == datetime(2026, 2, 28, 9, 0, tzinfo=UTC)
    assert e.next_occurrence(after=datetime(2026, 2, 28, 9, 0, tzinfo=UTC)) == datetime(2026, 3, 31, 9, 0, tzinfo=UTC)
