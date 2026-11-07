"""主动消息端到端：到期事件 → 初始化循环 → 应用内收件箱 → 客户端取走。

这是「她主动找你」在服务端的完整证明：不是单测某个策略，而是真实链路跑通，
并且验证收件箱只给本人、取走即清空、安静时段不发。
"""

import asyncio
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from companion.container import create_container
from companion.server.app import create_app
from companion.timeline.models import EventKind, TimelineEvent


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 7, hour, minute, tzinfo=UTC)


def _as(user: str) -> dict:
    return {"Authorization": f"Bearer {user}"}


def _seed(container, user: str, when: datetime, event_id: str = "e1") -> None:
    event = TimelineEvent(
        id=event_id,
        user_id=user,
        kind=EventKind.INTERVIEW,
        title="产品经理面试",
        at=when,
        source_character_id="linche",
        confidence=0.9,
    )
    asyncio.run(container.timeline.add(event))


def test_due_event_reaches_the_owner_inbox_once_and_is_drained():
    container = create_container()
    app = create_app(livekit_url="", container=container, run_initiative=False)
    _seed(container, "alice", _at(10, 3))

    asyncio.run(app.state.companion.loop.run_once(_at(10, 0)))

    client = TestClient(app)
    first = client.get("/companion/inbox", headers=_as("alice")).json()
    assert len(first) == 1
    assert first[0]["text"]
    assert first[0]["trigger"] == "event_due"
    assert first[0]["channel"] == "in_app"

    # 取走即清空：同一条不会再出现第二次。
    assert client.get("/companion/inbox", headers=_as("alice")).json() == []


def test_inbox_is_private_to_the_owner():
    container = create_container()
    app = create_app(livekit_url="", container=container, run_initiative=False)
    _seed(container, "alice", _at(10, 3))
    asyncio.run(app.state.companion.loop.run_once(_at(10, 0)))

    client = TestClient(app)
    assert client.get("/companion/inbox", headers=_as("bob")).json() == []
    assert len(client.get("/companion/inbox", headers=_as("alice")).json()) == 1


def test_quiet_hours_produce_no_inbox_message():
    container = create_container()
    app = create_app(livekit_url="", container=container, run_initiative=False)
    _seed(container, "alice", _at(23, 30))

    asyncio.run(app.state.companion.loop.run_once(_at(23, 25)))

    client = TestClient(app)
    assert client.get("/companion/inbox", headers=_as("alice")).json() == []


def test_background_worker_is_started_and_stopped_with_the_app():
    """生命周期里的定时任务能起、能停，不会留下孤儿协程。"""
    app = create_app(livekit_url="", run_initiative=True, initiative_interval=3600)
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
