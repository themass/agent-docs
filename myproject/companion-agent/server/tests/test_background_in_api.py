"""后台循环跟着 API 进程跑：开关、启停顺序、不阻塞响应、配置默认值。"""

from types import SimpleNamespace

import pytest

from companion.service.jobs.background import HEARTBEAT_SEC, BackgroundJobs
from companion.config import Settings


def test_the_setting_defaults_to_on_and_can_be_turned_off(monkeypatch):
    monkeypatch.delenv("COMPANION_JOBS_IN_API", raising=False)
    assert Settings(_env_file=None).companion_jobs_in_api is True
    monkeypatch.setenv("COMPANION_JOBS_IN_API", "false")
    assert Settings(_env_file=None).companion_jobs_in_api is False


class Platform:
    """够 BackgroundJobs 起循环用的最小平台：每个依赖都记一次调用。"""

    def __init__(self, tmp_path):
        self.started, self.redis = [], SimpleNamespace(set=self._set)
        self.jobs = SimpleNamespace(enqueue=self._enqueue, run_forever=self._run_forever)
        self.dispatcher = SimpleNamespace(run_once=self._ran_once)
        self.heartbeat_path = tmp_path / "hb"
        self.redis_calls = 0
        self.engine = object()          # 两个固定处理函数会拿它建存储；这里不会真的读写

    async def _set(self, *a, **kw):
        self.redis_calls += 1
        return True

    async def _enqueue(self, **kw):
        self.started.append(kw["kind"])

    async def _run_forever(self):
        import asyncio
        await asyncio.sleep(3600)

    async def _ran_once(self, now):
        self.started.append("reminder")


@pytest.fixture
def platform(monkeypatch, tmp_path):
    p = Platform(tmp_path)
    # 这些属性不存在也应当能起（缺哪块能力就不注册哪块）
    for name in ("pipeline", "resummarize", "timeline_recorder", "timeline", "persona_updater",
                 "account", "qa", "preferences", "ledger", "delivery", "compliance", "sessions", "chat"):
        setattr(p, name, None)
    monkeypatch.setattr("companion.service.jobs.background.build_initiative_loop", lambda p: _NoopLoop())
    return p


class _NoopLoop:
    def __init__(self):
        self.runs = 0

    async def run_once(self):
        self.runs += 1


async def test_start_launches_every_loop_and_stop_cancels_them(platform, tmp_path):
    jobs = BackgroundJobs(platform, heartbeat_path=str(platform.heartbeat_path))
    await jobs.start()
    assert jobs.running
    assert platform.heartbeat_path.exists()                 # 一起手就写一次心跳
    await jobs.stop()
    assert not jobs.running


async def test_stop_is_safe_to_call_twice_and_before_start():
    jobs = BackgroundJobs(SimpleNamespace())
    await jobs.stop()                                       # 没启动过
    await jobs.stop()                                       # 重复调用


async def test_the_heartbeat_file_carries_a_timestamp(platform):
    jobs = BackgroundJobs(platform, heartbeat_path=str(platform.heartbeat_path))
    jobs.heartbeat()
    text = platform.heartbeat_path.read_text()
    assert text.startswith("20") and "T" in text             # ISO 时间戳


def test_a_bad_heartbeat_path_is_not_fatal():
    jobs = BackgroundJobs(SimpleNamespace(), heartbeat_path="/nonexistent-dir/x/hb")
    jobs.heartbeat()            # 不抛


def test_the_heartbeat_interval_is_frequent_enough_to_matter():
    assert HEARTBEAT_SEC <= 60
