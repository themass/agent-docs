"""POST /v1/voice/script-sessions：剧本房会话发放。

房间名以 script- 开头；同一 case_id 在 lease TTL 内复用同一房间。
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from companion.api.http.deps import AllowAllVerifier, build_current_user
from companion.api.livekit.sessions_router import build_router as build_voice_router
from companion.devtools.script_room.lease import InMemoryScriptRoomLease
from companion.service.room.livekit_tokens import TokenMinter
from companion.service.room.sessions import InMemorySessionStore, SessionService

SECRET = "test-only-secret"
API_KEY = "test-api-key"
LIVEKIT_URL = "wss://livekit.example.test"


def _voice_client(*, lease=None, service=None):
    lease = lease or InMemoryScriptRoomLease()
    if service is None:
        service = SessionService(
            store=InMemorySessionStore(),
            minter=TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=600),
            livekit_url=LIVEKIT_URL,
            script_lease=lease,
        )
    app = FastAPI()
    app.include_router(
        build_voice_router(
            service,
            build_current_user(AllowAllVerifier()),
            chat_sessions=None,
            role_check=None,
            lease=lease,
        )
    )
    return TestClient(app), service, lease


def test_script_session_returns_script_room_prefix():
    client, _service, _lease = _voice_client()
    r = client.post(
        "/v1/voice/script-sessions",
        json={"character_id": "linche", "case_id": "barge_mid_sentence"},
        headers={"Authorization": "Bearer 1001"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["room_name"].startswith("script-")
    assert body["token"] and body["livekit_url"]


def test_script_session_same_case_reuses_room():
    client, _service, _lease = _voice_client()
    headers = {"Authorization": "Bearer 1001"}
    body = {"character_id": "linche", "case_id": "barge_mid_sentence"}
    a = client.post("/v1/voice/script-sessions", json=body, headers=headers).json()["room_name"]
    b = client.post("/v1/voice/script-sessions", json=body, headers=headers).json()["room_name"]
    assert a == b
    assert a.startswith("script-")
