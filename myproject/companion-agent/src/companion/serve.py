"""进程入口：带优雅停机的 uvicorn（P §3.5）。

收到第一次退出信号：置 draining（新发送 503，SSE 发 reconnect），等回合收尾至多 45 秒，
再交给 uvicorn 原本的 handle_exit。第二次信号立即退出。
"""

from __future__ import annotations

import asyncio
import os
import signal

import uvicorn

from companion.app.chat.lifecycle import DrainState

GRACE_SECONDS = 45.0


class DrainingServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, drain: DrainState, grace: float = GRACE_SECONDS) -> None:
        super().__init__(config)
        self._drain = drain
        self._grace = grace

    def handle_exit(self, sig: int, frame) -> None:  # noqa: ANN001 — uvicorn 签名
        if self._drain.draining:
            return super().handle_exit(sig, frame)
        self._drain.begin()
        asyncio.get_event_loop().create_task(self._graceful_exit(sig, frame))

    async def _graceful_exit(self, sig: int, frame) -> None:  # noqa: ANN001
        await self._drain.wait_idle(self._grace)
        super().handle_exit(sig, frame)


def main() -> None:
    from companion.bootstrap.app import create_app

    host = os.environ.get("COMPANION_HOST", "127.0.0.1")
    port = int(os.environ.get("COMPANION_PORT", "8081"))
    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_config=None)
    server = DrainingServer(config, app.state.companion.drain)
    server.run()


if __name__ == "__main__":
    main()
