"""重复跑真实的 job 进程冷初始化：对照 initialize_timeout 10s（SDK 默认）与 20s（修复候选）。

为什么要这个：2026-11-23/24 生产 voice.log 里 94+7 条 `error initializing process` 全是
`proc.initialize()` 的 wait_for TimeoutError——prewarm（import 清单 + catalog 扫盘 + VAD）
本体 cost_ms 5.3–8.6s（104 nproc=1），成功 init 的 elapsed_time 最高 9.99s 贴 10s 边。
要确认「20s 预算」是不是只是白送余量（不改冷路径耗时、不引入挂死风险），就在本地用
**同一个 SDK 构造**（ProcJobExecutor + 我们的 prewarm_fnc，和 ProcPool._proc_spawn_task
同一调用序：start → initialize → aclose）成对重复测。

它不连 LiveKit、不发合成、不碰数据库——只走进程 spawn + prewarm + 握手这一步。

用法（server/ 目录）：
    PYTHONPATH=src .venv/bin/python tools/qa_proc_init_timeout.py --trials 7
输出每 trial 的 elapsed/成败、两种预算的对比表。
"""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing as mp
import sys
import time

from companion.api.livekit.prewarm import prewarm


async def one_init(initialize_timeout: float, mp_ctx) -> tuple[bool, float]:
    """一次冷进程初始化：start → initialize（带 timeout）→ aclose。

    构造参数与 worker.py 装配 ProcPool 时下给每个 job 进程的完全一致（worker.py:627-647），
    唯一变量就是 initialize_timeout。entrypoint 用哑函数——本测只走到 InitializeResponse，
    不进任何房间。
    """
    from livekit.agents.ipc.job_proc_executor import ProcJobExecutor

    proc = ProcJobExecutor(
        initialize_process_fnc=prewarm,
        job_entrypoint_fnc=_noop_entry,
        session_end_fnc=None,
        simulation_end_fnc=None,
        inference_executor=None,
        initialize_timeout=initialize_timeout,
        close_timeout=10.0,
        session_end_timeout=300.0,
        memory_warn_mb=2000.0,
        memory_limit_mb=0.0,
        ping_interval=2.5,
        ping_timeout=60.0,
        high_ping_threshold=0.5,
        http_proxy=None,
        mp_ctx=mp_ctx,
        loop=asyncio.get_event_loop(),
    )
    t0 = time.perf_counter()
    ok = False
    try:
        await proc.start()
        await proc.initialize()
        ok = True
    except (TimeoutError, asyncio.TimeoutError):
        pass
    finally:
        await proc.aclose()
    return ok, (time.perf_counter() - t0) * 1000


async def _noop_entry(ctx) -> None:  # pragma: no cover - 永远不会被调到
    await ctx.connect()


async def run(trials: int, mp_ctx_str: str) -> int:
    mp_ctx = mp.get_context(mp_ctx_str)
    print(f"mp_ctx={mp_ctx_str} python={sys.version.split()[0]} trials={trials}")
    results: dict[float, list[tuple[bool, float]]] = {10.0: [], 20.0: []}
    for i in range(trials):
        for budget in (10.0, 20.0):
            ok, ms = await one_init(budget, mp_ctx)
            results[budget].append((ok, ms))
            print(f"trial={i} budget={budget:.0f}s ok={ok} elapsed_ms={ms:.0f}")

    print("\n== summary ==")
    for budget in (10.0, 20.0):
        rs = results[budget]
        ok_n = sum(1 for ok, _ in rs if ok)
        lat = sorted(ms for ok, ms in rs if ok)
        if lat:
            med = lat[len(lat) // 2]
            print(f"budget={budget:.0f}s success={ok_n}/{len(rs)} "
                  f"ok-latency_ms min={lat[0]:.0f} P50={med:.0f} max={lat[-1]:.0f}")
        else:
            print(f"budget={budget:.0f}s success=0/{len(rs)}")
    # 注意：budget=10 且失败的 trial，elapsed≈10s（被超时砍），不代表真实冷路径耗时——
    # 真实耗时看 budget=20 那一行（同一环境，同一 prewarm）。
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=7)
    ap.add_argument("--mp", default="forkserver", choices=("forkserver", "spawn"))
    raise SystemExit(asyncio.run(run(ap.parse_args().trials, ap.parse_args().mp)))
