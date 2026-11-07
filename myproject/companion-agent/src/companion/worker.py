"""worker 进程：把 entrypoint 交给 LiveKit 的 CLI 跑。

`WorkerOptions` 与 `cli.run_app` 是 LiveKit Agents 的标准启动方式；我们只提供装配，
不自己写调度——重连、并发、优雅退出都由框架负责，自己实现只会在边界情况下出错。
"""

from __future__ import annotations

import logging

from companion.config import settings


def main() -> None:
    logging.basicConfig(level=settings.companion_log_level)
    log = logging.getLogger("companion.worker")

    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        log.error("缺少 LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET，无法启动 worker")
        raise SystemExit(2)

    from companion.livekit_bridge import require

    require()

    from livekit.agents import WorkerOptions, cli

    from companion.agent.entrypoint import entrypoint

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
