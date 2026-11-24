"""隔离测 TTS 首帧：把「火山合成首包」从通话链路里单独量出来，给 F16 的 ③ 段定下界。

为什么要这个：生产 voice.log 里 ③（`tts start` → 首帧）冷轮 P50=7515ms、P95=12601ms，
但这个数字混了三件事——大脑第一句到得晚、job 子进程接房期的冷 import / 事件循环冻结、
火山合成本身。要知道「火山本身要多久」，只能在隔离环境里用**同一个构造路径**
（`bootstrap.voice_stack.build_tts`，和房间装配走的是同一个函数）单独发一句。

用法（在 server/ 目录）：
    PYTHONPATH=src .venv/bin/python tools/qa_tts_firstframe.py --mode fresh  # 每句新会话（模拟每 job 一次的冷路）
    PYTHONPATH=src .venv/bin/python tools/qa_tts_firstframe.py --mode reuse # 同一会话连发（模拟同通第二句起）
    可选 --env <path> 指定 .env；--n 控制句数（默认 6，省钱）。

它只发合成请求：不碰数据库、不碰对象存储、不动任何服务进程。凭据从 .env 读，
脚本不打印任何凭据。
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

SENTENCES = [
    "先歇一会儿，我在这儿陪着你。",
    "月亮掉进河里的那一晚，全镇的狗都没叫。",
    "我给你讲个很短的故事，大概二十秒。",
    "那盏灯一直亮着，等到很晚很晚。",
    "风把云推走了，星星就全露出来了。",
    "她抬头看月亮，月亮也在看她。",
]


def pct(values: list[float], p: float) -> float:
    v = sorted(values)
    return v[min(len(v) - 1, int(len(v) * p))]


async def one(tts_factory) -> float:
    """一句合成，返回「建流 → 首帧」毫秒数（与生产 ③ 同口径的引擎部分）。"""
    tts = tts_factory()
    stream = tts.stream()
    t0 = time.perf_counter()
    stream.push_text(SENTENCES[0])
    stream.end_input()
    first_ms: float | None = None
    async for ev in stream:
        if first_ms is None:
            first_ms = (time.perf_counter() - t0) * 1000
        # 首帧之后就别再收整段音频了，省流量也省时
        break
    await stream.aclose()
    return first_ms if first_ms is not None else float("nan")


async def run(mode: str, n: int, env_path: str | None) -> int:
    from companion.worker import load_env

    loaded = load_env(env_path) if env_path else load_env()
    if not loaded and not _has_keys():
        print("没读到 VOLC_TTS_API_KEY：用 --env 指定 .env")
        return 2

    from companion.bootstrap.voice_stack import build_tts, config_from_env

    config = config_from_env()

    def factory():
        # 与房间装配同一个构造：build_tts(config, voice_id=None)
        return build_tts(config)

    samples: list[float] = []
    if mode == "fresh":
        # 每句一个全新的 http_context + 新的 TTS 实例：一个 job 进程第一条 TTS 的形状
        from livekit.agents.utils import http_context

        for i in range(n):
            async with http_context.open():
                ms = await one(factory)
            samples.append(ms)
            print(f"fresh[{i}] first_frame_ms={ms:.0f}")
    else:
        from livekit.agents.utils import http_context

        async with http_context.open():
            for i in range(n):
                ms = await one(factory)
                samples.append(ms)
                print(f"reuse[{i}] first_frame_ms={ms:.0f}")
    ok = [s for s in samples if s == s]
    if not ok:
        print("没有有效样本")
        return 1
    print(f"\nmode={mode} n={len(ok)} min={min(ok):.0f} P50={pct(ok, .5):.0f} "
          f"P95={pct(ok, .95):.0f} max={max(ok):.0f} mean={statistics.mean(ok):.0f}")
    return 0


def _has_keys() -> bool:
    import os

    return bool((os.environ.get("VOLC_TTS_API_KEY") or "").strip())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("fresh", "reuse"), default="fresh")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--env", default=None)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args.mode, args.n, args.env)))
