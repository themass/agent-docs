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


def room_load(max_rooms: int) -> Callable[[Any], float]:
    """返回 ``load_fnc``：当前房间数占上限的比例（可以超过 1，表示已经超员）。"""
    if max_rooms < 1:
        raise ValueError("max_rooms must be >= 1")

    def load(server: Any) -> float:
        return len(server.active_jobs) / max_rooms

    return load


def worker_options_kwargs(max_rooms: int) -> dict[str, Any]:
    """给 ``WorkerOptions`` 的限流参数。``max_rooms <= 0`` 表示不限（沿用 SDK 默认的 CPU 判断）。"""
    if max_rooms <= 0:
        return {}
    return {"load_fnc": room_load(max_rooms), "load_threshold": FULL_AT}
