"""回合后的事件抽取与任务（chat-agent-timeline-design.md §5）。模型调用是脚本化的，不连真实模型。"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from companion.timeline.memory import InMemoryTimeline
from companion.app.jobs.handlers import timeline_record
from companion.timeline.recorder import TimelineRecorder
from companion.timeline.models import EventKind, EventOrigin, TimelineEvent


def _llm(payload):
    async def call(prompt: str) -> str:
        return json.dumps(payload, ensure_ascii=False)

    return call


def _item(title, at, confidence=0.9, kind="interview"):
    return {"kind": kind, "title": title, "at": at, "recurrence": "none", "confidence": confidence}


async def test_record_turn_writes_events_linked_to_the_message():
    at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    store = InMemoryTimeline()
    recorder = TimelineRecorder(store, _llm([_item("产品经理面试", at)]))
    saved = await recorder.record_turn(owner_id=7, role_id="linche", session_id=3, user_message_id=99,
                                       user_text="我后天有个面试", assistant_text="祝你顺利")
    assert len(saved) == 1
    event = saved[0]
    assert (event.source_message_id, event.session_id, event.origin) == ("99", 3, EventOrigin.EXTRACTED)
    assert [e.id for e in await store.by_source(owner_id="7", message_id="99")] == [event.id]


async def test_low_confidence_events_are_dropped():
    at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    recorder = TimelineRecorder(InMemoryTimeline(), _llm([_item("可能有个面试", at, confidence=0.2)]))
    assert await recorder.record_turn(owner_id=7, role_id="linche", session_id=3, user_message_id=1,
                                      user_text="好像后天面试？") == []


async def test_extraction_failure_is_not_an_error():
    async def broken(prompt: str) -> str:
        raise RuntimeError("model down")

    recorder = TimelineRecorder(InMemoryTimeline(), broken)
    assert await recorder.record_turn(owner_id=7, role_id="linche", session_id=3, user_message_id=1,
                                      user_text="我后天面试") == []


async def test_job_skips_a_closed_session():
    store = InMemoryTimeline()
    at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    recorder = TimelineRecorder(store, _llm([_item("面试", at)]))

    class Sessions:
        async def get(self, *, owner_id, session_id):
            return None

    handle = timeline_record(recorder, sessions=Sessions())
    await handle({"owner_id": 7, "session_id": 3, "role_id": "linche", "user_message_id": 1,
                  "user_text": "我后天面试"})
    assert await store.list_for_owner(owner_id="7", include_past=True) == []


async def test_tool_and_extraction_merge_into_one_event():
    """工具先记一次、回合后抽取再记一次：同一件事只留一条。"""
    store = InMemoryTimeline()
    at = datetime.now(UTC) + timedelta(days=2)
    tool = await store.upsert(TimelineEvent(id="", user_id="7", kind=EventKind.INTERVIEW, title="面试", at=at,
                                            source_character_id="linche", origin=EventOrigin.TOOL,
                                            session_id=3))
    recorder = TimelineRecorder(store, _llm([_item("面试", at.isoformat())]))
    saved = await recorder.record_turn(owner_id=7, role_id="linche", session_id=3, user_message_id=5,
                                       user_text="我后天面试")
    assert [e.id for e in saved] == [tool.id]
    assert len(await store.list_for_owner(owner_id="7", include_past=True)) == 1
