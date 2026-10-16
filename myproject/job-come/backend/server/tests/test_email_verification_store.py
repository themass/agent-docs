"""Regression coverage for dual-path email verification credentials."""

from __future__ import annotations

from jc.stores.email_verification_store import EmailVerificationStore


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str | int, *, ex: int) -> None:
        del ex
        self.values[key] = str(value)

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.values:
                removed += 1
                del self.values[key]
        return removed

    async def incr(self, key: str) -> int:
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value


async def test_verification_code_is_single_use_and_invalidates_link() -> None:
    store = EmailVerificationStore(FakeRedis())  # type: ignore[arg-type]
    await store.issue(
        user_id="usr_1",
        plain_token="link-token",
        verification_code="0420",
        ttl_seconds=60,
    )

    assert await store.verify_code(
        user_id="usr_1",
        verification_code="0420",
        max_attempts=5,
    ) == "verified"
    assert await store.consume_token("link-token") is None
    assert await store.verify_code(
        user_id="usr_1",
        verification_code="0420",
        max_attempts=5,
    ) == "expired"


async def test_resend_replaces_old_link_and_code() -> None:
    store = EmailVerificationStore(FakeRedis())  # type: ignore[arg-type]
    await store.issue(
        user_id="usr_1",
        plain_token="old-token",
        verification_code="1111",
        ttl_seconds=60,
    )
    await store.issue(
        user_id="usr_1",
        plain_token="new-token",
        verification_code="2222",
        ttl_seconds=60,
    )

    assert await store.consume_token("old-token") is None
    assert await store.verify_code(
        user_id="usr_1",
        verification_code="1111",
        max_attempts=5,
    ) == "invalid"
    assert await store.consume_token("new-token") == "usr_1"


async def test_verification_code_locks_after_attempt_limit() -> None:
    store = EmailVerificationStore(FakeRedis())  # type: ignore[arg-type]
    await store.issue(
        user_id="usr_1",
        plain_token="link-token",
        verification_code="0420",
        ttl_seconds=60,
    )

    for _ in range(5):
        assert await store.verify_code(
            user_id="usr_1",
            verification_code="9999",
            max_attempts=5,
        ) == "invalid"
    assert await store.verify_code(
        user_id="usr_1",
        verification_code="0420",
        max_attempts=5,
    ) == "locked"
