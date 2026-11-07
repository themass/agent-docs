"""建房：agent 入场只认房间 metadata，所以建房必须先于发 token，且失败即会话失败。"""

import pytest

from companion.server.sessions import InMemorySessionStore, SessionError, SessionService
from companion.server.tokens import TokenMinter

SECRET = "test-only-secret"
API_KEY = "test-api-key"
LIVEKIT_URL = "wss://livekit.example.test"


def _service(provision=None, store=None) -> SessionService:
    return SessionService(
        store=store or InMemorySessionStore(),
        minter=TokenMinter(api_key=API_KEY, api_secret=SECRET, ttl_sec=600),
        livekit_url=LIVEKIT_URL,
        provision_room=provision,
    )


async def test_room_is_provisioned_with_identity_before_the_token_is_issued():
    calls: list[tuple[str, dict[str, str]]] = []

    async def provision(room: str, metadata: dict[str, str]) -> None:
        calls.append((room, metadata))

    grant = await _service(provision).create(user_id="u1", character_id="linche")

    assert calls == [(grant.room_name, {"user_id": "u1", "character_id": "linche"})]


async def test_failed_room_creation_fails_the_session_and_stores_nothing():
    async def provision(room: str, metadata: dict[str, str]) -> None:
        raise RuntimeError("livekit unreachable")

    store = InMemorySessionStore()
    with pytest.raises(SessionError):
        await _service(provision, store).create(user_id="u1", character_id="linche")
    assert await store.list_for_user("u1") == []


async def test_without_a_provisioner_the_session_still_works_offline():
    grant = await _service(None).create(user_id="u1", character_id="linche")
    assert grant.room_name
    assert grant.token
