"""客户端依赖的接口：角色目录、记忆与事件、动作确认与偏好。

重点不是「能返回 200」，而是三件事：用户隔离（别人的数据看不见、改不了）、
分页边界（不会被一个大 limit 拖垮）、404 语义（不泄露「存在但不是你的」）。
"""

import asyncio

from fastapi.testclient import TestClient

from companion.bootstrap.platform import default_prompts
from companion.memory.port import MemoryItem
from companion.bootstrap.app import create_app
from companion.api.http.routers.memory import DEFAULT_PAGE, MAX_PAGE


def _platform():
    """有平台时 /v1 的路由才存在，且读的是 Postgres。测试数据必须经由它落库。"""
    import os

    from companion.brain.fake import FakeBrain
    from companion.memory.fake import InMemoryMemoryPort
    from companion.bootstrap.platform import build_platform
    from companion.config import Settings

    url = os.environ.get("COMPANION_TEST_DATABASE_URL") or os.environ.get("COMPANION_TEST_MYSQL_URL", "")
    settings = Settings(companion_mysql_url=url,
                        companion_redis_url=os.environ.get("COMPANION_TEST_REDIS_URL", ""))
    return build_platform(settings, brain=FakeBrain(["好"]), prompts=default_prompts(),
                          memory_port=InMemoryMemoryPort())


def _client(platform=None):
    return TestClient(create_app(livekit_url="",
                                 platform=platform or _platform()))


# /v1 的 owner id 是 BIGINT（与 Java 的 long 对齐），不能再用 "alice" 这类字符串。
# 名字映射成稳定数字，测试里仍然可以用人名读起来清楚。
_IDS = {"u1": 1001, "alice": 1002, "bob": 1003}


def _uid(name: str) -> int:
    return _IDS.get(name, 9000 + abs(hash(name)) % 1000)


def _as(user: str) -> dict:
    return {"Authorization": f"Bearer {_uid(user)}"}


def _seed_facts(platform, user: str, count: int) -> None:
    """写进平台用的那个记忆后端（/v1/memory/facts 读的就是它）。"""
    from companion.memory.subject import role_subject

    items = [
        MemoryItem(id=f"m{i}", content=f"事实{i}", source_character_id="linche")
        for i in range(count)
    ]
    asyncio.run(platform.memory.add(role_subject(str(_uid(user)), None), items))


def _pending_create(platform, user: str) -> str:
    """直接往确认存储写一条待确认。/v1/actions 读的就是它。

    ``Platform`` 没有暴露确认存储，用同一个 engine 建一个 store 即可——
    确认表是同一个库里的同一张表，不需要额外接线。
    """
    from datetime import UTC, datetime, timedelta

    from companion.store.sql import SqlConfirmationStore
    from companion.store.port import ConfirmationRecord

    # id 不能固定：同一个库上重复运行时主键会冲突（UniqueViolation）
    import uuid

    cid = f"cfm-{_uid(user)}-{uuid.uuid4().hex[:8]}"
    store = SqlConfirmationStore(platform.engine)
    # 确认动作执行时要能读到会话（create_reminder 会往会话里写），所以先建一个真会话
    session = asyncio.run(platform.sessions.create(owner_id=_uid(user), role_id="linche",
                                                   name="确认测试", locale="zh-CN"))
    record = ConfirmationRecord(
        id=cid, owner_id=_uid(user), session_id=session.id, turn_id=None, tool="create_reminder",
        args={"title": "吃药", "at": "2026-12-01T09:00:00+00:00"}, args_fingerprint="fp",
        title="建立提醒", summary="12 月 1 日提醒吃药", status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    asyncio.run(store.create(record))
    return cid


# ---- 角色目录 ----

def test_characters_are_listed_sorted_with_total():
    client = _client()
    body = client.get("/v1/characters", headers=_as("u1")).json()
    ids = [item["id"] for item in body["items"]]
    assert body["total"] >= 2
    assert ids == sorted(ids)


def test_character_detail_has_opening_line_and_no_creator_notes():
    client = _client()
    response = client.get("/v1/characters/linche", headers=_as("u1"))
    assert response.status_code == 200
    body = response.json()
    assert body["first_mes"]
    assert "creator_notes" not in body


def test_unknown_character_is_404():
    client = _client()
    assert client.get("/v1/characters/nobody", headers=_as("u1")).status_code == 404


def test_character_list_window_is_clamped_not_rejected():
    client = _client()
    response = client.get(
        "/v1/characters", params={"limit": 100000, "offset": -5}, headers=_as("u1")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] <= 100
    assert body["offset"] == 0


# ---- 记忆 ----

def test_memory_pages_report_has_more():
    platform = _platform()
    _seed_facts(platform, "u1", 5)
    client = _client(platform)

    first = client.get("/v1/memory/facts", params={"limit": 3}, headers=_as("u1")).json()
    assert len(first["items"]) == 3
    assert first["has_more"] is True

    last = client.get(
        "/v1/memory/facts", params={"limit": 3, "offset": 3}, headers=_as("u1")
    ).json()
    assert len(last["items"]) == 2
    assert last["has_more"] is False


def test_memory_limit_above_max_is_rejected():
    client = _client()
    response = client.get(
        "/v1/memory/facts", params={"limit": MAX_PAGE + 1}, headers=_as("u1")
    )
    assert response.status_code == 422


def test_memory_is_user_isolated():
    platform = _platform()
    _seed_facts(platform, "alice", 2)
    client = _client(platform)
    assert client.get("/v1/memory/facts", headers=_as("bob")).json()["items"] == []


def test_deleting_someone_elses_memory_looks_like_not_found():
    platform = _platform()
    _seed_facts(platform, "alice", 1)
    client = _client(platform)

    foreign = client.delete("/v1/memory/facts/m0", headers=_as("bob"))
    missing = client.delete("/v1/memory/facts/nope", headers=_as("bob"))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()

    assert client.delete("/v1/memory/facts/m0", headers=_as("alice")).status_code == 204
    assert client.get("/v1/memory/facts", headers=_as("alice")).json()["items"] == []


# ---- 事件 ----

def test_user_added_event_round_trips_with_full_confidence():
    client = _client()
    created = client.post(
        "/v1/memory/events",
        json={"title": "产品评审", "at": "2026-12-01T10:00:00+00:00", "kind": "meeting"},
        headers=_as("u1"),
    )
    assert created.status_code == 201
    assert created.json()["confidence"] == 1.0

    listed = client.get("/v1/memory/events", headers=_as("u1")).json()["items"]
    assert "产品评审" in [e["title"] for e in listed]


def test_event_title_length_is_validated():
    client = _client()
    response = client.post(
        "/v1/memory/events",
        json={"title": "x" * 61, "at": "2026-12-01T10:00:00+00:00"},
        headers=_as("u1"),
    )
    assert response.status_code == 422


def test_event_status_rejects_unknown_value():
    client = _client()
    created = client.post(
        "/v1/memory/events",
        json={"title": "面试", "at": "2026-12-01T10:00:00+00:00"},
        headers=_as("u1"),
    ).json()
    response = client.patch(f"/v1/memory/events/{created['id']}", json={"status": "bogus"},
                            headers=_as("u1"))
    assert response.status_code == 422


def test_event_mutation_is_user_isolated():
    client = _client()
    created = client.post(
        "/v1/memory/events",
        json={"title": "面试", "at": "2026-12-01T10:00:00+00:00"},
        headers=_as("alice"),
    ).json()
    event_id = created["id"]

    assert client.delete(f"/v1/memory/events/{event_id}", headers=_as("bob")).status_code == 404
    assert client.patch(f"/v1/memory/events/{event_id}", json={"status": "done"},
                        headers=_as("bob")).status_code == 404
    listed = client.get("/v1/memory/events", headers=_as("alice")).json()["items"]
    # 只断言「这条还在」：同一个库里可能有别的用例/上次运行留下的事件
    assert event_id in [e["id"] for e in listed]


def test_event_list_limit_is_bounded():
    client = _client()
    response = client.get(
        "/v1/memory/events", params={"limit": MAX_PAGE + 1}, headers=_as("u1")
    )
    assert response.status_code == 422


# ---- 动作确认 ----

def test_pending_actions_are_listed_per_user():
    platform = _platform()
    cid = _pending_create(platform, "alice")
    client = _client(platform)

    mine = client.get("/v1/actions/pending", headers=_as("alice")).json()["items"]
    ids = [item["confirmation_id"] for item in mine]
    assert cid in ids, "本次建的待确认必须在列表里"
    assert client.get("/v1/actions/pending", headers=_as("bob")).json()["items"] == []


def test_confirm_by_stranger_is_404_and_does_not_consume():
    platform = _platform()
    cid = _pending_create(platform, "alice")
    client = _client(platform)

    stranger = client.post(
        f"/v1/actions/{cid}/confirm", json={"accepted": True}, headers=_as("bob")
    )
    assert stranger.status_code == 404
    ids = [i["confirmation_id"] for i in client.get("/v1/actions/pending", headers=_as("alice")).json()["items"]]
    assert cid in ids, "陌生人的确认不能把它消费掉"


def test_decline_consumes_the_confirmation():
    platform = _platform()
    cid = _pending_create(platform, "alice")
    client = _client(platform)

    response = client.post(
        f"/v1/actions/{cid}/confirm", json={"accepted": False}, headers=_as("alice")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "declined"
    assert body.get("message_id"), "拒绝后会补一条「已取消」的说明消息"
    ids = [i["confirmation_id"] for i in client.get("/v1/actions/pending", headers=_as("alice")).json()["items"]]
    assert cid not in ids, "拒绝之后这条不该还挂在待办里"


def test_accept_executes_and_cannot_be_replayed():
    platform = _platform()
    cid = _pending_create(platform, "alice")
    client = _client(platform)

    response = client.post(
        f"/v1/actions/{cid}/confirm", json={"accepted": True}, headers=_as("alice")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "executed"

    again = client.post(
        f"/v1/actions/{cid}/confirm", json={"accepted": True}, headers=_as("alice")
    )
    assert again.status_code == 404


# ---- 偏好 ----

def test_prefs_default_to_initiative_defaults():
    client = _client()
    body = client.get("/v1/prefs", headers=_as("u1")).json()
    assert body["events_enabled"] is True
    assert body["greetings_enabled"] is False
    assert body["call_enabled"] is False
    assert body["quiet_start"] == "23:00"


def test_prefs_patch_only_touches_given_fields_and_is_per_user():
    client = _client()
    updated = client.put(
        "/v1/prefs",
        json={"greetings_enabled": True, "quiet_start": "22:30"},
        headers=_as("alice"),
    ).json()
    assert updated["greetings_enabled"] is True
    assert updated["quiet_start"] == "22:30"
    assert updated["events_enabled"] is True

    bob = client.get("/v1/prefs", headers=_as("bob")).json()
    assert bob["greetings_enabled"] is False


def test_empty_paused_until_resumes_a_paused_user():
    client = _client()
    client.put("/v1/prefs", json={"paused_until": "2030-01-01T00:00:00Z"}, headers=_as("u1"))
    assert client.get("/v1/prefs", headers=_as("u1")).json()["paused_until"] is not None

    resumed = client.put("/v1/prefs", json={"paused_until": ""}, headers=_as("u1")).json()
    assert resumed["paused_until"] is None


def test_prefs_wrong_type_is_rejected():
    client = _client()
    response = client.put("/v1/prefs", json={"max_per_day": "lots"}, headers=_as("u1"))
    assert response.status_code == 422
