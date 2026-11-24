"""语音房间并发上限：负载函数、与 SDK 的“满”判断对接、配置默认值。"""

import math
from types import SimpleNamespace

import pytest

from companion.api.livekit.capacity import (
    FULL_AT,
    INITIALIZE_PROCESS_TIMEOUT_S,
    room_load,
    worker_options_kwargs,
)


def server(n_rooms):
    return SimpleNamespace(active_jobs=[object()] * n_rooms)


def is_full(load, threshold=FULL_AT):
    """SDK 的判断：有效负载 >= 阈值 就报“已满”（worker.py 的 _update_worker_status）。"""
    return load >= threshold


@pytest.mark.parametrize("rooms,full", [(0, False), (1, False), (4, False), (5, True), (6, True), (9, True)])
def test_a_worker_reports_full_exactly_when_it_reaches_the_cap(rooms, full):
    assert is_full(room_load(5)(server(rooms))) is full


def test_the_load_is_the_share_of_the_cap():
    assert room_load(4)(server(1)) == 0.25 and room_load(4)(server(2)) == 0.5


def test_a_cap_of_one_means_one_room_per_worker():
    load = room_load(1)
    assert not is_full(load(server(0))) and is_full(load(server(1)))


def test_the_threshold_is_valid_in_production():
    # SDK 在生产环境要求阈值不超过 1，超过会告警
    assert FULL_AT <= 1.0 and not math.isinf(FULL_AT)


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_cap_is_rejected_by_the_load_function(bad):
    with pytest.raises(ValueError):
        room_load(bad)


def test_zero_means_unlimited_and_passes_no_load_options():
    # 不限流时只剩进程初始化预算一项——限流相关的键一个都不带。
    kw = worker_options_kwargs(0)
    assert kw == {"initialize_process_timeout": INITIALIZE_PROCESS_TIMEOUT_S}
    kw = worker_options_kwargs(-3)
    assert kw == {"initialize_process_timeout": INITIALIZE_PROCESS_TIMEOUT_S}


def test_a_positive_cap_sets_both_the_function_and_the_threshold():
    kw = worker_options_kwargs(5)
    assert set(kw) == {"load_fnc", "load_threshold", "initialize_process_timeout"}
    assert kw["load_threshold"] == FULL_AT
    assert kw["load_fnc"](server(5)) == 1.0


def test_the_options_are_accepted_by_the_real_worker_options_class():
    """不靠猜：用 SDK 真实的 WorkerOptions 接一遍，参数名写错会在这里直接报。"""
    from livekit.agents import WorkerOptions

    opts = WorkerOptions(entrypoint_fnc=lambda ctx: None, **worker_options_kwargs(5))
    assert opts.load_threshold == FULL_AT and opts.load_fnc(server(3)) == 0.6
    opts.validate_config(devmode=False)        # 生产模式的校验不报错


def test_the_timeout_reaches_the_real_worker_options_class():
    """生产 94+7 条 `error initializing process` 全是 initialize 的 10s wait_for 超时。
    预算必须真的挂进 SDK（名字写错=白改），而且比 SDK 默认（10.0s）宽。"""
    from livekit.agents import WorkerOptions

    opts = WorkerOptions(entrypoint_fnc=lambda ctx: None,
                         **worker_options_kwargs(5, port=8091))
    assert opts.initialize_process_timeout == INITIALIZE_PROCESS_TIMEOUT_S
    default_opts = WorkerOptions(entrypoint_fnc=lambda ctx: None)
    assert INITIALIZE_PROCESS_TIMEOUT_S > default_opts.initialize_process_timeout


def _hang_forever(_proc):
    """挂死替身：forkserver 要 pickle 它，所以必须放模块级。"""
    import time

    time.sleep(30)


async def _unused_entry(_ctx):
    """entrypoint 走不到（进程在 initialize 就被掐），同样要模块级可 pickle。"""
    raise AssertionError("entrypoint 不该被调到")


async def test_a_hanging_prewarm_is_still_killed_at_the_budget():
    """放宽预算不等于放弃看门狗：挂死的 prewarm 到点仍被 initialize 的 wait_for 掐掉
    （20s 候选的安全性质——SDK 对任何预算值都执行同样的超时+重试路径）。用 0.5s 预算演示。

    构造与 worker 装配 ProcPool 时下给 job 进程的同一形状（ProcJobExecutor），
    只是 initialize_process_fnc 换成一个睡 30s 的挂死替身。"""
    import asyncio
    import multiprocessing
    import time

    from livekit.agents.ipc.job_proc_executor import ProcJobExecutor

    proc = ProcJobExecutor(
        initialize_process_fnc=_hang_forever,
        job_entrypoint_fnc=_unused_entry,
        session_end_fnc=None,
        simulation_end_fnc=None,
        inference_executor=None,
        initialize_timeout=0.5,
        close_timeout=5.0,
        session_end_timeout=300.0,
        memory_warn_mb=2000.0,
        memory_limit_mb=0.0,
        ping_interval=2.5,
        ping_timeout=60.0,
        high_ping_threshold=0.5,
        http_proxy=None,
        mp_ctx=multiprocessing.get_context("forkserver"),
        loop=asyncio.get_event_loop(),
    )
    t0 = time.perf_counter()
    killed = False
    try:
        await proc.start()
        await proc.initialize()
    except TimeoutError:
        killed = True
    finally:
        await proc.aclose()
    assert killed and time.perf_counter() - t0 < 10


def test_the_setting_has_a_conservative_default_and_reads_the_env(monkeypatch):
    from companion.config import Settings

    monkeypatch.delenv("COMPANION_VOICE_MAX_ROOMS", raising=False)
    assert Settings(_env_file=None).companion_voice_max_rooms == 5
    monkeypatch.setenv("COMPANION_VOICE_MAX_ROOMS", "12")
    assert Settings(_env_file=None).companion_voice_max_rooms == 12
