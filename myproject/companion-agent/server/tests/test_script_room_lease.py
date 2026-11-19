"""剧本房 lease：TTL 过期 + Redis NX 竞争后不无条件 SET。"""

import pytest

from companion.bootstrap.app import _default_script_lease
from companion.bootstrap.checks import StartupRefused
from companion.devtools.script_room.lease import InMemoryScriptRoomLease, RedisScriptRoomLease
from companion.service.room.sessions import SCRIPT_ROOM_PREFIX


class _Clock:
    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.mark.asyncio
async def test_memory_lease_expires_and_reallocates():
    clock = _Clock(0.0)
    lease = InMemoryScriptRoomLease(ttl_sec=10, _now=clock)
    first = await lease.attach("barge_mid_sentence")
    assert first.startswith(SCRIPT_ROOM_PREFIX)
    assert await lease.attach("barge_mid_sentence") == first

    clock.t = 10.0  # 刚好到期
    second = await lease.attach("barge_mid_sentence")
    assert second.startswith(SCRIPT_ROOM_PREFIX)
    assert second != first


class _FakeRedis:
    """可控的 SET NX / GET：模拟赢家过期后两输家抢占。"""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple] = []
        self._nx_fail_then_empty = 0  # 前 N 次 NX 返回 False 且 GET 为空

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        self.set_calls.append((key, value, nx, ex))
        if nx:
            if self._nx_fail_then_empty > 0:
                self._nx_fail_then_empty -= 1
                return False
            if key in self.store:
                return False
            self.store[key] = value
            return True
        self.store[key] = value
        return True


@pytest.mark.asyncio
async def test_redis_lease_retries_nx_instead_of_blind_set():
    redis = _FakeRedis()
    # 第一次 SET NX「输」且 GET 空（模拟赢家刚过期）；第二次 NX 成功
    redis._nx_fail_then_empty = 1
    lease = RedisScriptRoomLease(redis=redis, ttl_sec=600)
    room = await lease.attach("case_a")
    assert room.startswith(SCRIPT_ROOM_PREFIX)
    assert redis.store[f"ca:script:lease:case_a"] == room
    # 所有写入都必须带 nx=True——禁止无条件 SET
    assert all(call[2] is True for call in redis.set_calls)
    assert len(redis.set_calls) == 2


@pytest.mark.asyncio
async def test_redis_lease_loser_reads_winner_room():
    redis = _FakeRedis()
    redis.store["ca:script:lease:case_b"] = "script-case_b-winner"
    lease = RedisScriptRoomLease(redis=redis)
    assert await lease.attach("case_b") == "script-case_b-winner"
    assert redis.set_calls == []


def test_bootstrap_non_dev_fail_closed_without_redis_url():
    class S:
        companion_env = "prod"
        companion_redis_url = ""

    with pytest.raises(StartupRefused, match="companion_redis_url"):
        _default_script_lease(S())


def test_bootstrap_dev_allows_memory_without_redis():
    class S:
        companion_env = "dev"
        companion_redis_url = ""

    lease = _default_script_lease(S())
    assert isinstance(lease, InMemoryScriptRoomLease)
