"""客户端依赖的接口：角色目录、记忆与事件、动作确认与偏好。

重点不是「能返回 200」，而是三件事：用户隔离（别人的数据看不见、改不了）、
分页边界（不会被一个大 limit 拖垮）、404 语义（不泄露「存在但不是你的」）。
"""

import asyncio

from fastapi.testclient import TestClient

from companion.actions.executor import ActionRequest
from companion.container import create_container
from companion.memory.port import MemoryItem
from companion.server.app import create_app
from companion.server.memory_api import DEFAULT_PAGE, MAX_PAGE


def _client(container=None):
    return TestClient(create_app(livekit_url="", container=container or create_container()))


def _as(user: str) -> dict:
    return {"Authorization": f"Bearer {user}"}


def _seed_facts(container, user: str, count: int) -> None:
    items = [
        MemoryItem(id=f"m{i}", content=f"事实{i}", source_character_id="linche")
        for i in range(count)
    ]
    asyncio.run(container.memory.add(user, items))


def _pending_create(container, user: str) -> str:
    """直接走执行器造一条待确认，避免依赖某个具体动作的业务细节。"""
    request = ActionRequest(
        name="create_reminder",
        arguments={"title": "吃药", "at": "2026-12-01T09:00:00+00:00"},
        user_id=user,
        character_id="linche",
    )
    outcome = asyncio.run(container.executor.execute(request))
    assert outcome.status == "needs_confirmation"
    return outcome.confirmation_id


# ---- 角色目录 ----

def test_characters_are_listed_sorted_with_total():
    client = _client()
    body = client.get("/companion/characters", headers=_as("u1")).json()
    ids = [item["id"] for item in body["items"]]
    assert body["total"] >= 2
    assert ids == sorted(ids)


def test_character_detail_has_opening_line_and_no_creator_notes():
    client = _client()
    response = client.get("/companion/characters/linche", headers=_as("u1"))
    assert response.status_code == 200
    body = response.json()
    assert body["first_mes"]
    assert "creator_notes" not in body


def test_unknown_character_is_404():
    client = _client()
    assert client.get("/companion/characters/nobody", headers=_as("u1")).status_code == 404


def test_character_list_window_is_clamped_not_rejected():
    client = _client()
    response = client.get(
        "/companion/characters", params={"limit": 100000, "offset": -5}, headers=_as("u1")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] <= 100
    assert body["offset"] == 0


# ---- 记忆 ----

def test_memory_pages_report_has_more():
    container = create_container()
    _seed_facts(container, "u1", 5)
    client = _client(container)

    first = client.get("/companion/memory", params={"limit": 3}, headers=_as("u1")).json()
    assert len(first["items"]) == 3
    assert first["has_more"] is True

    last = client.get(
        "/companion/memory", params={"limit": 3, "offset": 3}, headers=_as("u1")
    ).json()
    assert len(last["items"]) == 2
    assert last["has_more"] is False


def test_memory_limit_above_max_is_rejected():
    client = _client()
    response = client.get(
        "/companion/memory", params={"limit": MAX_PAGE + 1}, headers=_as("u1")
    )
    assert response.status_code == 422


def test_memory_is_user_isolated():
    container = create_container()
    _seed_facts(container, "alice", 2)
    client = _client(container)
    assert client.get("/companion/memory", headers=_as("bob")).json()["items"] == []


def test_deleting_someone_elses_memory_looks_like_not_found():
    container = create_container()
    _seed_facts(container, "alice", 1)
    client = _client(container)

    foreign = client.delete("/companion/memory/m0", headers=_as("bob"))
    missing = client.delete("/companion/memory/nope", headers=_as("bob"))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()

    assert client.delete("/companion/memory/m0", headers=_as("alice")).status_code == 204
    assert client.get("/companion/memory", headers=_as("alice")).json()["items"] == []


# ---- 事件 ----

def test_user_added_event_round_trips_with_full_confidence():
    client = _client()
    created = client.post(
        "/companion/events",
        json={"title": "产品评审", "at": "2026-12-01T10:00:00+00:00", "kind": "meeting"},
        headers=_as("u1"),
    )
    assert created.status_code == 201
    assert created.json()["confidence"] == 1.0

    listed = client.get("/companion/events", headers=_as("u1")).json()
    assert [e["title"] for e in listed] == ["产品评审"]


def test_event_title_length_is_validated():
    client = _client()
    response = client.post(
        "/companion/events",
        json={"title": "x" * 61, "at": "2026-12-01T10:00:00+00:00"},
        headers=_as("u1"),
    )
    assert response.status_code == 422


def test_event_status_rejects_unknown_value():
    client = _client()
    created = client.post(
        "/companion/events",
        json={"title": "面试", "at": "2026-12-01T10:00:00+00:00"},
        headers=_as("u1"),
    ).json()
    response = client.post(f"/companion/events/{created['id']}/bogus", headers=_as("u1"))
    assert response.status_code == 422


def test_event_mutation_is_user_isolated():
    client = _client()
    created = client.post(
        "/companion/events",
        json={"title": "面试", "at": "2026-12-01T10:00:00+00:00"},
        headers=_as("alice"),
    ).json()
    event_id = created["id"]

    assert client.delete(f"/companion/events/{event_id}", headers=_as("bob")).status_code == 404
    assert client.post(f"/companion/events/{event_id}/done", headers=_as("bob")).status_code == 404
    listed = client.get("/companion/events", headers=_as("alice")).json()
    assert [e["id"] for e in listed] == [event_id]


def test_event_list_limit_is_bounded():
    client = _client()
    response = client.get(
        "/companion/events", params={"limit": MAX_PAGE + 1}, headers=_as("u1")
    )
    assert response.status_code == 422


# ---- 动作确认 ----

def test_pending_actions_are_listed_per_user():
    container = create_container()
    cid = _pending_create(container, "alice")
    client = _client(container)

    mine = client.get("/companion/actions/pending", headers=_as("alice")).json()
    assert [item["confirmation_id"] for item in mine] == [cid]
    assert client.get("/companion/actions/pending", headers=_as("bob")).json() == []


def test_confirm_by_stranger_is_404_and_does_not_consume():
    container = create_container()
    cid = _pending_create(container, "alice")
    client = _client(container)

    stranger = client.post(
        f"/companion/actions/{cid}/confirm", json={"accepted": True}, headers=_as("bob")
    )
    assert stranger.status_code == 404
    assert len(client.get("/companion/actions/pending", headers=_as("alice")).json()) == 1


def test_decline_consumes_the_confirmation():
    container = create_container()
    cid = _pending_create(container, "alice")
    client = _client(container)

    response = client.post(
        f"/companion/actions/{cid}/confirm", json={"accepted": False}, headers=_as("alice")
    )
    assert response.status_code == 200
    assert response.json() == {"status": "declined"}
    assert client.get("/companion/actions/pending", headers=_as("alice")).json() == []


def test_accept_executes_and_cannot_be_replayed():
    container = create_container()
    cid = _pending_create(container, "alice")
    client = _client(container)

    response = client.post(
        f"/companion/actions/{cid}/confirm", json={"accepted": True}, headers=_as("alice")
    )
    assert response.status_code == 200
    assert response.json()["status"] == "executed"

    again = client.post(
        f"/companion/actions/{cid}/confirm", json={"accepted": True}, headers=_as("alice")
    )
    assert again.status_code == 404


# ---- 偏好 ----

def test_prefs_default_to_initiative_defaults():
    client = _client()
    body = client.get("/companion/prefs", headers=_as("u1")).json()
    assert body["events_enabled"] is True
    assert body["greetings_enabled"] is False
    assert body["call_enabled"] is False
    assert body["quiet_start"] == "23:00"


def test_prefs_patch_only_touches_given_fields_and_is_per_user():
    client = _client()
    updated = client.put(
        "/companion/prefs",
        json={"greetings_enabled": True, "quiet_start": "22:30"},
        headers=_as("alice"),
    ).json()
    assert updated["greetings_enabled"] is True
    assert updated["quiet_start"] == "22:30"
    assert updated["events_enabled"] is True

    bob = client.get("/companion/prefs", headers=_as("bob")).json()
    assert bob["greetings_enabled"] is False


def test_empty_paused_until_resumes_a_paused_user():
    client = _client()
    client.put("/companion/prefs", json={"paused_until": "2030-01-01T00:00:00Z"}, headers=_as("u1"))
    assert client.get("/companion/prefs", headers=_as("u1")).json()["paused_until"] is not None

    resumed = client.put("/companion/prefs", json={"paused_until": ""}, headers=_as("u1")).json()
    assert resumed["paused_until"] is None


def test_prefs_wrong_type_is_rejected():
    client = _client()
    response = client.put("/companion/prefs", json={"max_per_day": "lots"}, headers=_as("u1"))
    assert response.status_code == 422
