"""Redis naming contract tests."""

from __future__ import annotations

import pytest

from jc.redis_client import redis_key, redis_key_prefix
from jc.stores.email_verification_store import EmailVerificationStore
from jc.stores.guest_session_store import GuestSessionStore


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.last_key: str | None = None

    async def set(self, key: str, value: str, **_: object) -> None:
        self.last_key = key
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        self.last_key = key
        return self.data.get(key)

    async def delete(self, key: str) -> int:
        self.last_key = key
        return int(self.data.pop(key, None) is not None)

    async def getdel(self, key: str) -> str | None:
        self.last_key = key
        return self.data.pop(key, None)


def test_redis_keys_include_application_environment_and_namespace(monkeypatch) -> None:
    from jc import redis_client

    monkeypatch.setattr(redis_client.settings, "jc_redis_key_prefix", "jc:dev:")
    assert redis_key_prefix("session") == "jc:dev:session:"
    assert redis_key("email-verify", "token_hash") == "jc:dev:email-verify:token_hash"


def test_guest_store_uses_shared_redis_key_builder(monkeypatch) -> None:
    from jc import redis_client

    monkeypatch.setattr(redis_client.settings, "jc_redis_key_prefix", "jc:test:")
    store = GuestSessionStore(None)  # type: ignore[arg-type]
    assert store._guest_key("gst_test") == "jc:test:guest:gst_test"


@pytest.mark.asyncio
async def test_email_verification_store_uses_shared_redis_key_builder(monkeypatch) -> None:
    from jc import redis_client

    monkeypatch.setattr(redis_client.settings, "jc_redis_key_prefix", "jc:test:")
    redis = FakeRedis()
    store = EmailVerificationStore(redis)  # type: ignore[arg-type]

    await store.save(user_id="usr_test", plain_token="plain_token", ttl_seconds=60)

    assert redis.last_key is not None
    assert redis.last_key.startswith("jc:test:email-verify:")


