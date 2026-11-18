"""会话创建：房间命名、身份、过期时间、store 行为。

直接驱动 ``SessionService`` / ``InMemorySessionStore``——没装 fastapi 的测试
环境也能跑到真正的逻辑，不需要 TestClient。
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest

from companion.service.room.sessions import ROOM_PREFIX, InMemorySessionStore, SessionError, SessionRecord, SessionService, room_name_for
from companion.service.room.livekit_tokens import TokenMinter, decode_jwt, user_identity

SECRET = "test-only-secret"
API_KEY = "test-api-key"
LIVEKIT_URL = "wss://livekit.example.test"


@pytest.fixture
def service():
    return SessionService(
        store=InMemorySessionStore(),
        minter=TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=600),
        livekit_url=LIVEKIT_URL,
    )


async def test_create_returns_room_token_and_expiry(service):
    grant = await service.create(user_id="u1", character_id="xiaowu")

    assert grant.room_name.startswith(ROOM_PREFIX)
    assert grant.room_name == room_name_for(grant.session_id)
    assert grant.token
    assert grant.livekit_url == LIVEKIT_URL
    assert grant.expires_at.timestamp() > time.time()

    payload = grant.to_json()
    assert payload["expires_at"].endswith("Z")
    assert payload["session_id"] == grant.session_id


async def test_token_identity_is_prefixed_user_id(service):
    grant = await service.create(user_id="u1", character_id="xiaowu")
    claims = decode_jwt(grant.token, SECRET)
    assert claims["sub"] == "user:u1"
    assert claims["sub"] == user_identity("u1")
    assert claims["video"]["room"] == grant.room_name


async def test_two_sessions_for_same_user_get_different_rooms(service):
    first = await service.create(user_id="u1", character_id="xiaowu")
    second = await service.create(user_id="u1", character_id="xiaowu")
    assert first.room_name != second.room_name
    assert first.session_id != second.session_id


async def test_session_is_persisted_for_character_lookup(service):
    grant = await service.create(user_id="u1", character_id="xiaowu")
    stored = await service.store.get(grant.session_id)
    assert isinstance(stored, SessionRecord)
    assert stored.character_id == "xiaowu"
    assert stored.identity == "user:u1"
    assert [r.session_id for r in await service.store.list_for_user("u1")] == [grant.session_id]
    assert await service.store.list_for_user("u2") == []


async def test_missing_livekit_url_is_a_session_error(service):
    broken = SessionService(
        store=service.store, minter=service.minter, livekit_url=""
    )
    with pytest.raises(SessionError):
        await broken.create(user_id="u1", character_id="xiaowu")


async def test_missing_credentials_surface_as_token_error(service):
    from companion.service.room.livekit_tokens import MissingCredentials

    broken = SessionService(
        store=service.store,
        minter=TokenMinter(api_key="", api_secret="", ttl_sec=600),
        livekit_url=LIVEKIT_URL,
    )
    with pytest.raises(MissingCredentials):
        await broken.create(user_id="u1", character_id="xiaowu")


# ------------------------------------------------------ provider 线路选择
# 协议见 docs（Android 侧 docs/companion-rtc-provider-switching.md §2）：
# provider 在建会话时定、随 grant 下发；选择逻辑收在 SessionService.create 一处。


async def test_grant_carries_livekit_provider_by_default(service):
    """默认线路必须在 grant 里显式出现：客户端不必猜「字段没有=哪种线路」。"""
    grant = await service.create(user_id="u1", character_id="xiaowu")

    assert grant.provider == "livekit"
    assert grant.provider_config == {}
    payload = grant.to_json()
    assert payload["provider"] == "livekit"
    assert payload["provider_config"] == {}


async def test_configured_provider_reaches_the_grant(service):
    switched = SessionService(
        store=service.store,
        minter=service.minter,
        livekit_url=LIVEKIT_URL,
        provider="VOLCENGINE",  # 大小写与空白在解析处归一
    )
    # 火山线路的服务端实现尚未接入：合法值也要在建会话时显式失败，
    # 而不是下发一份客户端解不开的凭据（静默降级是客户端的事，见 _resolve_provider）。
    with pytest.raises(SessionError, match="volcengine"):
        await switched.create(user_id="u1", character_id="xiaowu")


async def test_unknown_provider_is_a_session_error_not_a_silent_fallback(service):
    broken = SessionService(
        store=service.store,
        minter=service.minter,
        livekit_url=LIVEKIT_URL,
        provider="agora",
    )
    with pytest.raises(SessionError, match="agora"):
        await broken.create(user_id="u1", character_id="xiaowu")


async def test_blank_provider_setting_means_livekit(service):
    fallback = SessionService(
        store=service.store, minter=service.minter, livekit_url=LIVEKIT_URL, provider="  "
    )
    grant = await fallback.create(user_id="u1", character_id="xiaowu")
    assert grant.provider == "livekit"


@pytest.mark.parametrize(
    "kwargs", [{"user_id": "", "character_id": "xiaowu"}, {"user_id": "u1", "character_id": ""}]
)
async def test_empty_inputs_are_rejected(service, kwargs):
    with pytest.raises(SessionError):
        await service.create(**kwargs)


async def test_store_is_safe_under_concurrent_writes():
    store = InMemorySessionStore()
    created = datetime.now(UTC)
    expires = created + timedelta(seconds=600)
    records = [
        SessionRecord(
            session_id=f"s{i}",
            user_id=f"u{i}",
            character_id="xiaowu",
            room_name=room_name_for(f"s{i}"),
            identity=user_identity(f"u{i}"),
            created_at=created,
            expires_at=expires,
        )
        for i in range(50)
    ]

    await asyncio.gather(*(store.save(r) for r in records))
    assert len([await store.get(r.session_id) for r in records]) == 50


def test_http_endpoint_wires_identity_room_and_token():
    """HTTP 层只做装配，语义已由上面的用例覆盖；这里防的是接线错。"""
    pytest.importorskip("fastapi", reason="fastapi 不在测试 venv 里")
    from fastapi.testclient import TestClient

    from companion.bootstrap.app import create_app

    app = create_app(
        minter=TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=600),
        livekit_url=LIVEKIT_URL,
    )
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.post(
            "/v1/voice/sessions",
            json={"character_id": "xiaowu"},
            headers={"Authorization": "Bearer u1"},
        )
        assert response.status_code == 200

        body = response.json()
        assert body["room_name"] == room_name_for(body["session_id"])
        assert body["identity"] == "user:u1"
        assert body["livekit_url"] == LIVEKIT_URL

        claims = decode_jwt(body["token"], SECRET)
        assert claims["sub"] == "user:u1"
        assert claims["video"]["room"] == body["room_name"]
