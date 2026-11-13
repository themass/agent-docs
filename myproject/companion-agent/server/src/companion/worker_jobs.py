"""后台任务进程入口 —— **可选**的独立运行方式。

默认这些循环跟着 API 进程跑（``COMPANION_JOBS_IN_API=true``，只需在一个副本上开）。
想分开部署时用这个入口：``python -m companion.worker_jobs``。
两种方式可以并存，不会重复发：任务队列用 FOR UPDATE SKIP LOCKED 认领，主动开口用 Redis SET NX 抢占。

循环本身在 ``app/jobs/background.py``，这里只做装配与启动。
"""

from __future__ import annotations

import asyncio
import logging
import os


async def main() -> None:
    from companion.app.jobs.background import run_forever
    from companion.bootstrap.platform import build_platform, default_prompts
    from companion.config import settings

    logging.basicConfig(level=os.environ.get("COMPANION_LOG_LEVEL", "INFO"))
    platform = build_platform(settings, prompts=default_prompts(), profile="jobs")
    await platform.astart()
    try:
        await run_forever(platform)
    finally:
        await platform.aclose()


if __name__ == "__main__":
    asyncio.run(main())
