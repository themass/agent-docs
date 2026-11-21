"""位置消息（P2-13）：发送、落库、历史回读。

位置**不占附件通道**（没有 upload_id，也不该被 mime 闸门管）：走 SendBody 的
``location`` 字段，落库成 ``kind="location"`` 的用户消息，``content`` 自动生成一行
模型可读的文本，结构化坐标存 ``meta.location`` 并由历史接口原样带回。
"""

import asyncio
import os
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REDIS_URL = os.environ.get("COMPANION_TEST_REDIS_URL", "")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="COMPANION_TEST_REDIS_URL not set")


class Sessions:
    def __init__(self):
        self.rows = {}

    async def get(self, *, owner_id, session_id):
        r = self.rows.get(session_id)
        return r if r and r.owner_id == owner_id else None

    async def create(self, *, owner_id, role_id, name, locale):
        sid = len(self.rows) + 1
        r = SimpleNamespace(id=sid, owner_id=owner_id, role_id=role_id, name=name, locale=locale,
                            updated_at=datetime.now(UTC))
        self.rows[sid] = r
        return r


class Messages:
    def __init__(self):
        self.rows = {}
        self.next_id = 1

    async def append(self, *, owner_id, session_id, role, content, kind, client_message_id, turn_id, meta):
        m = SimpleNamespace(id=self.next_id, owner_id=owner_id, session_id=session_id, role=role,
                            content=content, kind=kind, client_message_id=client_message_id,
                            turn_id=turn_id, interrupted=False, created_at=datetime.now(UTC),
                            deleted=False, meta=meta, alt_group=None)
        self.next_id += 1
        self.rows[m.id] = m
        return m

    async def alt_ids_for(self, *, owner_id, session_id, groups):
        return {}

    async def find_by_client_id(self, **kw):
        return None

    async def list_before(self, *, owner_id, session_id, before_id, limit):
        return [m for m in self.rows.values() if m.owner_id == owner_id and m.session_id == session_id][:limit]

    async def attach_turn(self, *, owner_id, session_id, message_ids, turn_id):
        for mid in message_ids:
            if mid in self.rows:
                self.rows[mid].turn_id = turn_id
        return len(message_ids)

    async def mark_interrupted(self, **kw):
        return True

    async def list_by_turn(self, *, owner_id, session_id, turn_id):
        return [m for m in self.rows.values() if m.turn_id == turn_id and not m.deleted]


class Queue:
    def __init__(self):
        self.items = []

    async def enqueue(self, *, owner_id, session_id, message_id, client_message_id, text):
        item = SimpleNamespace(id=len(self.items) + 1, owner_id=owner_id, session_id=session_id,
                               message_id=message_id, text=text, status="queued", drain_attempts=0)
        self.items.append(item)
        return item

    async def list_queued(self, *, owner_id, session_id):
        return [i for i in self.items if i.status == "queued" and i.owner_id == owner_id]

    async def list_status(self, *, owner_id, session_id, status):
        return [i for i in self.items if i.status == status and i.owner_id == owner_id]

    async def transition(self, *, item_id, from_status, to_status, turn_id=None):
        for i in self.items:
            if i.id == item_id and i.status == from_status:
                i.status = to_status
                return True
        return False


@pytest.fixture
def env():
    import redis.asyncio as redis

    from companion.agent.brain.port import TextDelta
    from companion.api.http.deps import AllowAllVerifier, build_current_user
    from companion.api.http.routers.chat import build_router
    from companion.bootstrap.chat_stack import build_chat_api
    from companion.service.chat.lifecycle import DrainState
    from companion.service.turn.redis_control import RedisTurnControl

    client = redis.from_url(REDIS_URL, decode_responses=False)

    async def produce(request, inbox):
        await asyncio.sleep(0.02)
        yield TextDelta("好的")

    sessions, messages, queue = Sessions(), Messages(), Queue()
    api, _close = build_chat_api(sessions=sessions, messages=messages, queue=queue,
                                 control=RedisTurnControl(client), produce=produce,
                                 drain=DrainState(), process_name="test")
    app = FastAPI()
    app.include_router(build_router(api, build_current_user(AllowAllVerifier())))
    yield SimpleNamespace(app=app, sessions=sessions, messages=messages)


ME = {"Authorization": "Bearer 7"}


def _session(env):
    http = TestClient(env.app)
    sid = http.post("/v1/sessions", json={"role_id": "linche", "name": "位置"}, headers=ME).json()["id"]
    return http, sid


def test_location_message_lands_as_location_kind_with_readable_content(env):
    http, sid = _session(env)
    r = http.post(f"/v1/sessions/{sid}/messages",
                  json={"location": {"lat": 31.23, "lng": 121.47, "accuracy_m": 120}}, headers=ME)
    assert r.status_code == 202, r.text

    row = next(m for m in env.messages.rows.values() if m.role == "user")
    assert row.kind == "location"
    assert "31.23" in row.content and "121.47" in row.content  # 模型读 content 文本，零改动可见
    assert row.meta["location"]["lat"] == 31.23 and row.meta["location"]["lng"] == 121.47
    assert row.meta["location"]["accuracy_m"] == 120


def test_location_with_text_keeps_user_text_as_content(env):
    http, sid = _session(env)
    r = http.post(f"/v1/sessions/{sid}/messages",
                  json={"text": "我在这", "location": {"lat": 1.5, "lng": 2.5}}, headers=ME)
    assert r.status_code == 202, r.text

    row = next(m for m in env.messages.rows.values() if m.role == "user")
    assert row.kind == "location"
    assert row.content == "我在这"
    assert row.meta["location"] == {"lat": 1.5, "lng": 2.5}


def test_history_returns_the_location_field(env):
    http, sid = _session(env)
    http.post(f"/v1/sessions/{sid}/messages",
              json={"location": {"lat": 31.23, "lng": 121.47}}, headers=ME)
    items = http.get(f"/v1/sessions/{sid}/messages", headers=ME).json()["items"]
    msg = next(m for m in items if m["kind"] == "location")
    assert msg["location"] == {"lat": 31.23, "lng": 121.47}
    # 普通文字消息不能被带上 location 键
    assert all("location" not in m for m in items if m["kind"] != "location")


def test_out_of_range_coordinates_are_rejected(env):
    http, sid = _session(env)
    for bad in ({"lat": 91, "lng": 0}, {"lat": 0, "lng": 181}, {"lat": -90.1, "lng": 0}):
        r = http.post(f"/v1/sessions/{sid}/messages", json={"location": bad}, headers=ME)
        assert r.status_code == 422, (bad, r.text)


def test_empty_send_without_text_attachment_or_location_is_rejected(env):
    """原来「text 与 attachments 至少一个」的边界加上 location：三者全空必须拒。"""
    http, sid = _session(env)
    r = http.post(f"/v1/sessions/{sid}/messages", json={}, headers=ME)
    assert r.status_code in (400, 422), r.text


def test_video_attachment_keeps_duration_in_meta(env):
    """视频卡片要显示时长；pydantic 默认丢弃未声明字段，所以 duration_s 必须是模型字段，
    否则发送时带的时长到不了 meta，接收方刷新历史后卡片只剩文件名。"""
    http, sid = _session(env)
    r = http.post(f"/v1/sessions/{sid}/messages",
                  json={"attachments": [{"upload_id": "01" + "V" * 24, "kind": "video",
                                         "name": "海边.mp4", "duration_s": 42}]}, headers=ME)
    assert r.status_code == 202, r.text

    row = next(m for m in env.messages.rows.values() if m.role == "user")
    att = row.meta["attachments"][0]
    assert att["kind"] == "video" and att["name"] == "海边.mp4" and att["duration_s"] == 42

    items = http.get(f"/v1/sessions/{sid}/messages", headers=ME).json()["items"]
    assert items[0]["attachments"][0]["duration_s"] == 42
