"""常驻热池：通话到来时 job 进程池必须已经是热的，补池不得在通话窗口里再烧一次冷 import。

livekit-agents 1.8.11 的语义（proc_pool.py / worker.py，以已装版本为准）：
- `num_idle_processes` 默认 `ServerEnvOption(prod_default=min(ceil(cpu_count),4))`。
  104（Ubuntu 20.04，cgroup v1 无配额）上 SDK 落到 `CGroupV1CPUMonitor`，
  `cpu_count()` 回退 **2.0**（实机验证）——热池变成 2 个 ~540MB 常驻进程，
  且通话时 `set_target_idle_processes` 仍按 default=2 补，1 活跃房间 = 3 个进程并存，
  2GB 机器顶不住（journalctl 实测：两个 idle 进程各 RSS 542MB/545MB）。
- forkserver 的 `preload_modules` 不设，`set_forkserver_preload` 就只带 SDK 自带的
  两个模块（生产 journal：`packages: ["livekit.agents.ipc._preload", ...]`）——
  每个 job 进程都在 `prewarm_fnc` 里重付 27 项冷 import（生产 cost_ms 9323–9971）。
  18:52 那通实证：job 本身吃到了热进程（RoomIO pid=1398825，18:49:49 已 init），
  `cost_ms=9971` 那行是**补池**进程（pid 1399489）——9–10s 的 import 风暴正砸在
  通话进行中的单核上。清单交给 forkserver，全 worker 生命周期只付一次，
  子进程 COW 继承，`prewarm_fnc` 只剩查表 + VAD load + catalog。

这里钉装配：值对、名字对（挂进真实 WorkerOptions/AgentServer，写错=白改），
沿用 test_voice_capacity 的钉法。
"""

from __future__ import annotations

from companion.api.livekit.capacity import (
    WARM_IDLE_PROCESSES,
    worker_options_kwargs,
)
from companion.api.livekit.prewarm import PREWARM_IMPORTS


def test_exactly_one_warm_process_stands_by():
    """热池常驻 1 个热进程：够接住下一通，又不让 2GB 机器并存两份 ~540MB。"""
    assert WARM_IDLE_PROCESSES == 1
    assert worker_options_kwargs(5)["num_idle_processes"] == WARM_IDLE_PROCESSES


def test_the_warm_slot_survives_the_unlimited_cap():
    """num_idle_processes 与限流无关——不限流时也必须带（同 initialize_process_timeout）。"""
    kw = worker_options_kwargs(0)
    assert kw["num_idle_processes"] == WARM_IDLE_PROCESSES


def test_the_warm_slot_reaches_the_real_worker_options():
    """参数名写错 SDK 会静默用默认（=cgroup 假 cpu_count 决定的 2），这里必须咬住。"""
    from livekit.agents import WorkerOptions

    opts = WorkerOptions(
        entrypoint_fnc=lambda ctx: None, **worker_options_kwargs(5, port=8091)
    )
    assert opts.num_idle_processes == WARM_IDLE_PROCESSES
    opts.validate_config(devmode=False)


def test_the_agent_server_carries_the_pool_target_into_construction():
    """装配到底：`AgentServer.from_server_options` 必须真的把 num_idle_processes 传给构造。

    只构造不 run——`_proc_pool` 要到 run() 才存在，这里钉的是构造参数被接住
    （名字接错 SDK 会静默用默认值 = cgroup 假 cpu_count 决定的 2）。
    """
    from livekit.agents import WorkerOptions
    from livekit.agents.worker import AgentServer

    opts = WorkerOptions(
        entrypoint_fnc=lambda ctx: None, **worker_options_kwargs(5, port=0)
    )
    server = AgentServer.from_server_options(opts)
    assert server._num_idle_processes == WARM_IDLE_PROCESSES


def test_the_prewarm_list_is_handed_to_the_forkserver():
    """27 项重 import 在 forkserver 里付一次，job 进程 COW 继承——补池不再冷烧。"""
    kw = worker_options_kwargs(5)
    assert kw["preload_modules"] == list(PREWARM_IMPORTS)


def test_the_preload_modules_reach_the_real_worker_options():
    """`preload_modules` 只在 forkserver 上下文生效（spawn 下 no-op）；Linux 生产正是
    forkserver。名字拼错 WorkerOptions 直接 TypeError，这条钉的就是它存在且值对。"""
    from livekit.agents import WorkerOptions

    opts = WorkerOptions(
        entrypoint_fnc=lambda ctx: None, **worker_options_kwargs(5, port=8091)
    )
    assert opts.preload_modules == list(PREWARM_IMPORTS)
