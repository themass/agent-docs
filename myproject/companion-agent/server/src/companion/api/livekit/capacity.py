"""语音房间并发上限：一个 worker 进程最多同时接多少个房间。

为什么要自己限：LiveKit 默认按 CPU 占用判断“满没满”（生产默认 0.7）。语音 agent 大部分时间在等网络，
CPU 很低，所以按 CPU 永远不会满，房间会一直接。而我们的瓶颈是**数据库连接**：每个房间是一个独立进程，
各自一份连接池（最多 6 条），房间一多就会把库的连接数占满。

做法：负载 = 当前房间数 / 上限，阈值设为 1.0。房间数到上限时 worker 报“已满”，LiveKit 不再把新房间派给它。
这是**单个 worker 进程**的上限；总容量 = 上限 × worker 进程数。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# 阈值的取值：负载到 1.0（房间数 == 上限）就算满。SDK 要求生产环境阈值不超过 1。
FULL_AT = 1.0

# 常驻热 job 进程数。SDK 默认 `min(ceil(cpu_count),4)`——但 104（Ubuntu 20.04、cgroup v1
# 无配额）上 `CGroupV1CPUMonitor.cpu_count()` 回退 **2.0**（实机验证），热池成了 2 个
# ~540MB 常驻进程（journalctl 实测 idle RSS 542MB/545MB），通话时补池还按 default=2 追：
# 1 活跃房间 = 3 进程并存，2GB 机器顶不住。显式 1：接住下一通够用，内存峰值可控。
WARM_IDLE_PROCESSES = 1

# job 进程 initialize/prewarm 的预算。SDK 默认 10.0s（worker.py:219），生产实测顶不住：
# 2026-11-23/24 voice.log 94+7 条 `error initializing process` 全是这条 wait_for 的
# TimeoutError——prewarm 本体（import 清单 + catalog 扫盘 + VAD）cost_ms 5.3–8.6s
# （104 nproc=1），成功 init 的 elapsed_time 最高 9.99s 贴边；失败子 pid 全部缺
# `prewarm done` 行（被杀在 prewarm 中途），每次白烧 10s + 一整轮重生，用户端是
# 拨号后 10–30s 静默。2a098aa 把清单补到 27 项后 10s 更不够（生产 venv 冷 import
# 单项就 9.2s）。显式 20s：prewarm 有头，真挂死仍会触发重试。
INITIALIZE_PROCESS_TIMEOUT_S = 20.0


def room_load(max_rooms: int) -> Callable[[Any], float]:
    """返回 ``load_fnc``：当前房间数占上限的比例（可以超过 1，表示已经超员）。"""
    if max_rooms < 1:
        raise ValueError("max_rooms must be >= 1")

    def load(server: Any) -> float:
        return len(server.active_jobs) / max_rooms

    return load


def worker_options_kwargs(max_rooms: int, *, port: int | None = None) -> dict[str, Any]:
    """给 ``WorkerOptions`` 的装配参数：限流、进程初始化预算、健康检查端口。

    ``max_rooms <= 0`` 表示不限流（沿用 SDK 默认的 CPU 判断）。

    ``port`` 是 worker 自己的健康检查 HTTP 端口（不是我们的业务端口）。SDK 在生产模式下默认 8081，
    和 ``companion.serve`` 的默认端口撞车——两个进程在同一台机器上部署时，后起的那个绑不上
    ``[Errno 98] address already in use`` 然后退出。部署时给它一个单独的端口。

    ``initialize_process_timeout`` 无条件带上：job 进程 prewarm 的预算（见
    ``INITIALIZE_PROCESS_TIMEOUT_S``），与限流无关，所以不跟 max_rooms 的条件走。

    ``num_idle_processes`` 同样无条件带上：常驻 1 个热 job 进程（见
    ``WARM_IDLE_PROCESSES``）。不显式设的话生产默认按 cpu_count 算，104 上 SDK 的
    cgroup-v1 监视器回退 2.0——两个热进程 + 通话中补池，内存直接越线。

    ``preload_modules`` 把 prewarm 的 import 清单交给 forkserver（`set_forkserver_preload`，
    worker.py:786）：重 import 在 forkserver 里只付一次，每个 job 进程 COW 继承，
    ``prewarm_fnc`` 里只剩 sys.modules 查表。不设的话（现状）forkserver 只带 SDK 自带两个
    模块，每个 job——包括通话中途补池的那个——都要重烧一遍 27 项冷 import（生产
    cost_ms 9323–9971 的单核风暴，正砸在通话进行中的 ICE/媒体窗口上）。spawn 上下文
    （macOS 开发机）下该参数是 no-op，prewarm_fnc 仍逐项执行，行为不变。
    """
    from companion.api.livekit.prewarm import PREWARM_IMPORTS

    kwargs: dict[str, Any] = {
        "initialize_process_timeout": INITIALIZE_PROCESS_TIMEOUT_S,
        "num_idle_processes": WARM_IDLE_PROCESSES,
        "preload_modules": list(PREWARM_IMPORTS),
    }
    if max_rooms > 0:
        kwargs.update(load_fnc=room_load(max_rooms), load_threshold=FULL_AT)
    if port:
        kwargs["port"] = port
    return kwargs
